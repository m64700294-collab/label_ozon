import streamlit as st
import re
from io import BytesIO
from pypdf import PdfReader, PdfWriter

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Универсальный Сортировщик Ozon", page_icon="📦")

st.title("📦 Универсальный сортировщик Ozon")
st.write("Скрипт сам найдет названия товаров на этикетках и сгруппирует их. Поддерживает любые артикулы.")

def extract_product_name(text):
    """
    Пытается найти название товара на этикетке.
    Логика: ищем текст после заголовка 'Наименование' или 'Артикул Наименование'.
    """
    # Очищаем текст от лишних пробелов для поиска
    clean_text = text.replace('\n', '  ')
    
    # 1. Попытка найти стандартный заголовок Ozon
    # Обычно идет: "Артикул Наименование" (перенос строки) "Название товара..."
    match = re.search(r'Наименование\s+(.+?)(\s\d+:20|\s\d{10,}|\s*$)', clean_text)
    
    if match:
        # Берем найденное название, обрезаем лишнее
        name = match.group(1).strip()
        # Если название слишком длинное (захватило лишний текст), обрезаем
        if len(name) > 60:
            name = name[:60] + "..."
        return name
    
    # 2. Если не нашли, пробуем взять просто первую длинную строку (как резерв)
    lines = text.split('\n')
    for line in lines:
        if len(line) > 10 and "Отгрузка" not in line and "FBS" not in line and "ПВЗ" not in line:
            return line.strip()
            
    return "Нераспознанный товар"

def process_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    writer = PdfWriter()
    num_pages = len(reader.pages)
    
    labels_data = []
    
    # Прогресс-бар
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i in range(0, num_pages, 2):
        # Обновляем прогресс
        progress = int((i / num_pages) * 100)
        progress_bar.progress(progress)
        
        if i + 1 >= num_pages: break
        
        page_1 = reader.pages[i]
        page_2 = reader.pages[i+1]
        text = page_2.extract_text()
        
        # --- 1. АВТОМАТИЧЕСКОЕ ОПРЕДЕЛЕНИЕ НАЗВАНИЯ ---
        product_name = extract_product_name(text)

        # --- 2. ОПРЕДЕЛЕНИЕ КОЛИЧЕСТВА ---
        qty = 1
        match_qty_header = re.search(r'•\s*(\d+)\s*шт', text)
        match_qty_x = re.search(r'[x×]\s?(\d+)\b', text)
        
        if match_qty_header:
            qty = int(match_qty_header.group(1))
        elif match_qty_x:
            found_num = int(match_qty_x.group(1))
            if found_num < 50: qty = found_num
        
        labels_data.append({
            "p1": page_1,
            "p2": page_2,
            "name": product_name, # Теперь сортируем по реальному имени
            "qty": qty,
            "orig_index": i
        })

    progress_bar.progress(100)
    
    # --- 3. СОРТИРОВКА ---
    # Сначала по Имени (алфавит), потом по Количеству, потом по порядку
    sorted_labels = sorted(labels_data, key=lambda x: (x['name'], x['qty'], x['orig_index']))
    
    # Сборка
    for item in sorted_labels:
        writer.add_page(item['p1'])
        writer.add_page(item['p2'])
        
    output = BytesIO()
    writer.write(output)
    output.seek(0)
    
    return output, sorted_labels

# --- ИНТЕРФЕЙС ---
uploaded_file = st.file_uploader("Загрузите файл PDF", type="pdf")

if uploaded_file is not None:
    if st.button("🚀 Сортировать все товары"):
        with st.spinner('Анализирую товары...'):
            try:
                processed_pdf, stats = process_pdf(uploaded_file)
                
                st.success(f"Готово! Обработано {len(stats)} этикеток.")
                
                # Показываем, какие товары нашел скрипт
                st.subheader("📦 Найденные группы товаров:")
                
                # Считаем статистику
                counts = {}
                for item in stats:
                    key = f"{item['name']} (x{item['qty']})"
                    counts[key] = counts.get(key, 0) + 1
                
                # Вывод таблицы с количеством
                for name, count in counts.items():
                    st.write(f"🔹 **{name}**: {count} шт.")

                st.download_button(
                    label="📥 Скачать отсортированный PDF",
                    data=processed_pdf,
                    file_name="СОРТИРОВКА_ВСЕ_ТОВАРЫ.pdf",
                    mime="application/pdf",
                    type="primary"
                )
                
            except Exception as e:
                st.error(f"Ошибка: {e}")
