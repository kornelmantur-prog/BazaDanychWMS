import streamlit as st
from supabase import create_client, Client
import pandas as pd

# 1. Konfiguracja Strony
st.set_page_config(page_title="Prosty WMS", layout="wide")
st.title("📦 System WMS - Magazyn")

# 2. Połączenie z Supabase
# Pobieramy dane z sekretów (lokalnie .streamlit/secrets.toml lub Secrets w chmurze)
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Nie udało się połączyć z bazą danych. Sprawdź plik secrets.toml.")
    st.stop()

# --- FUNKCJE POMOCNICZE ---

def pobierz_kategorie():
    """Pobiera listę kategorii do wyboru w formularzu."""
    response = supabase.table('kategorie').select("*").execute()
    return response.data

def pobierz_produkty():
    """Pobiera produkty wraz z nazwami kategorii."""
    # Pobieramy produkty i łączymy (join) z tabelą kategorie
    response = supabase.table('Produkt').select("*, kategorie(nazwa)").execute()
    data = response.data
    
    # Spłaszczanie struktury danych dla ładniejszej tabeli (wyciągamy nazwę kategorii)
    cleaned_data = []
    for item in data:
        kategoria_nazwa = item['kategorie']['nazwa'] if item['kategorie'] else "Brak"
        cleaned_data.append({
            "ID": item['id'],
            "Nazwa Produktu": item['nazwa'],
            "Ilość": item['liczba'],
            "Cena": item['cena'],
            "Kategoria": kategoria_nazwa
        })
    return cleaned_data

def dodaj_kategorie(nazwa, opis):
    try:
        data = {"nazwa": nazwa, "opis": opis}
        supabase.table('kategorie').insert(data).execute()
        st.success(f"Dodano kategorię: {nazwa}")
    except Exception as e:
        st.error(f"Błąd podczas dodawania kategorii: {e}")

def dodaj_produkt(nazwa, liczba, cena, kategoria_id):
    try:
        data = {
            "nazwa": nazwa,
            "liczba": int(liczba),
            "cena": float(cena),
            "kategoria_ID": int(kategoria_id)
        }
        supabase.table('Produkt').insert(data).execute()
        st.success(f"Dodano produkt: {nazwa}")
    except Exception as e:
        st.error(f"Błąd podczas dodawania produktu: {e}")

# --- INTERFEJS UŻYTKOWNIKA (UI) ---

# Zakładki dla lepszej organizacji
tab1, tab2, tab3 = st.tabs(["📋 Stan Magazynowy", "➕ Dodaj Produkt", "🏷️ Dodaj Kategorię"])

# --- ZAKŁADKA 1: STAN MAGAZYNOWY ---
with tab1:
    st.header("Aktualny stan magazynu")
    
    # Przycisk odświeżania
    if st.button("Odśwież dane"):
        st.rerun()

    produkty_data = pobierz_produkty()
    
    if produkty_data:
        df = pd.DataFrame(produkty_data)
        # Formatowanie kolumn
        st.dataframe(
            df,
            column_config={
                "Cena": st.column_config.NumberColumn(format="%.2f PLN"),
                "Ilość": st.column_config.NumberColumn(format="%d szt.")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Szybkie statystyki
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Łączna liczba produktów", len(df))
        with col2:
            wartosc_calkowita = sum(p['Cena'] * p['Ilość'] for p in produkty_data)
            st.metric("Wartość magazynu", f"{wartosc_calkowita:.2f} PLN")
    else:
        st.info("Magazyn jest pusty.")

# --- ZAKŁADKA 2: DODAJ PRODUKT ---
with tab2:
    st.header("Przyjęcie towaru")
    
    # Najpierw musimy pobrać kategorie, żeby wyświetlić je w liście rozwijanej
    cats = pobierz_kategorie()
    
    if not cats:
        st.warning("Najpierw dodaj przynajmniej jedną kategorię w zakładce 'Dodaj Kategorię'.")
    else:
        # Tworzymy słownik {Nazwa Kategorii: ID Kategorii}
        mapa_kategorii = {c['nazwa']: c['id'] for c in cats}
        
        with st.form("form_produkt"):
            p_nazwa = st.text_input("Nazwa Produktu")
            col_a, col_b = st.columns(2)
            with col_a:
                p_ilosc = st.number_input("Ilość (szt.)", min_value=1, step=1)
            with col_b:
                p_cena = st.number_input("Cena (PLN)", min_value=0.01, step=0.01)
            
            p_kategoria_nazwa = st.selectbox("Wybierz kategorię", options=list(mapa_kategorii.keys()))
            
            submitted_prod = st.form_submit_button("Zapisz produkt")
            
            if submitted_prod:
                if p_nazwa:
                    cat_id = mapa_kategorii[p_kategoria_nazwa]
                    dodaj_produkt(p_nazwa, p_ilosc, p_cena, cat_id)
                    st.rerun() # Odśwież stronę, żeby zaktualizować tabelę
                else:
                    st.error("Nazwa produktu jest wymagana.")

# --- ZAKŁADKA 3: DODAJ KATEGORIĘ ---
with tab3:
    st.header("Nowa Kategoria")
    
    with st.form("form_kategoria"):
        k_nazwa = st.text_input("Nazwa Kategorii")
        k_opis = st.text_area("Opis (opcjonalnie)")
        
        submitted_kat = st.form_submit_button("Dodaj kategorię")
        
        if submitted_kat:
            if k_nazwa:
                dodaj_kategorie(k_nazwa, k_opis)
                st.rerun()
            else:
                st.error("Nazwa kategorii nie może być pusta.")
