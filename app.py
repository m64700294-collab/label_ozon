import streamlit as st
import re
import os
from io import BytesIO
from datetime import datetime # Добавили работу с датой
from pypdf import PdfReader, PdfWriter

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Сортировщик Ozon", page_icon="📦")

st.title("📦 Печать этикеток Ozon")
st.write("Загрузите файл. Скрипт сохранит его с исходным именем + текущая дата.")

def extract_product_name(text):
    """
    Пытается найти название товара на этикетке.
    """
    clean_text = text.replace('\n', '  ')
    
    # 1. Попытка найти стандартный заголовок Ozon
    match = re.search(r'Наименование\s+(.+?)(\s\d+:20|\s\d{10,}|\s*$)', clean_text)
    
    if match:
        name = match.group(1).strip()
        if len(name) > 60:
            name = name[:60] + "..."
        return name
    
    # 2. Резервный поиск
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
    
    progress_bar = st.progress(0)
    
    for i in range(0, num_pages, 2):
        progress = int((i / num_pages) * 100)
        progress_bar.progress(progress)
        
        if i + 1 >= num_pages: break
        
        page_1 = reader.pages[i]
        page_2 = reader.pages[i+1]
        text = page_2.extract_text()
        
        # 1. Название
        product_name = extract_product_name(text)

        # 2. Количество
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
            "name": product_name,
            "qty": qty,
            "orig_index": i
        })

    progress_bar.progress(100)
    
    # Сортировка
    sorted_labels = sorted(labels_data, key=lambda x: (x['name'], x['qty'], x['orig_index']))
    
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
    # ---------------------------------------------------------
    # ЛОГИКА ФОРМИРОВАНИЯ ИМЕНИ ФАЙЛА
    # 1. Берем имя исходного файла (например "Андреев.pdf")
    original_filename = uploaded_file.name
    
    # 2. Убираем расширение .pdf (получаем "Андреев")
    file_base = os.path.splitext(original_filename)[0]
    
    # 3. Получаем текущую дату (День-Месяц-Год)
    current_date = datetime.now().strftime("%d-%m-%Y")
    
    # 4. Собираем новое имя: "Андреев_SORTED_04-01-2026.pdf"
    new_filename = f"{file_base}_SORTED_{current_date}.pdf"
    # ---------------------------------------------------------

    if st.button("🚀 Сортировать"):
        with st.spinner('Обработка...'):
            try:
                processed_pdf, stats = process_pdf(uploaded_file)
                
                st.success(f"Готово! Файл будет называться: {new_filename}")
                
                # Статистика
                counts = {}
                for item in stats:
                    key = f"{item['name']} (x{item['qty']})"
                    counts[key] = counts.get(key, 0) + 1
                
                for name, count in counts.items():
                    st.write(f"🔹 **{name}**: {count} шт.")

                # Кнопка скачивания с НОВЫМ именем
                st.download_button(
                    label=f"📥 Скачать {new_filename}",
                    data=processed_pdf,
                    file_name=new_filename, # <--- Сюда подставляем нашу переменную
                    mime="application/pdf",
                    type="primary"
                )
                
            except Exception as e:
                st.error(f"Ошибка: {e}")
