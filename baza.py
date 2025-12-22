import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS System", layout="wide", page_icon="📦")
st.title("📦 System WMS - Zarządzanie Magazynem")

# --- 2. POŁĄCZENIE Z BAZĄ DANYCH ---
try:
    # Pobieranie sekretów z pliku .streamlit/secrets.toml lub Streamlit Cloud Secrets
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("🔴 Błąd połączenia z bazą danych. Sprawdź plik secrets.toml.")
    st.info("Szczegóły błędu: " + str(e))
    st.stop()

# --- 3. FUNKCJE OBSŁUGI BAZY (CRUD) ---

def pobierz_dane():
    """Pobiera produkty i kategorie, zwraca DataFrame i surowe dane."""
    try:
        # Pobieramy produkty z relacją do kategorii
        # UWAGA: Supabase/Postgres często zmienia nazwy kolumn na małe litery
        response = supabase.table('Produkt').select("*, kategorie(nazwa)").execute()
        data = response.data
        
        cleaned_data = []
        for item in data:
            # Bezpieczne pobieranie nazwy kategorii (jeśli brak, wpisz "Brak")
            kat_nazwa = item.get('kategorie', {}).get('nazwa') if item.get('kategorie') else "Brak"
            
            # Bezpieczne pobieranie ID kategorii (sprawdza Kategoria_ID oraz kategoria_ID)
            kat_id_safe = item.get('Kategoria_ID', item.get('kategoria_ID'))
            
            cleaned_data.append({
                "ID": item['id'],
                "Nazwa": item['nazwa'],
                "Ilość": item['liczba'],
                "Cena": item['cena'],
                "Kategoria": kat_nazwa,
                "Kategoria_ID": kat_id_safe 
            })
        
        return pd.DataFrame(cleaned_data), cleaned_data
    except Exception as e:
        st.error(f"Błąd podczas pobierania danych: {e}")
        return pd.DataFrame(), []

def pobierz_liste_kategorii():
    res = supabase.table('kategorie').select("*").execute()
    return res.data

def dodaj_produkt_db(nazwa, liczba, cena, kat_id):
    try:
        # Tutaj używamy klucza 'kategoria_ID' (z małej litery), bo tak zazwyczaj oczekuje Supabase
        data = {
            "nazwa": nazwa,
            "liczba": int(liczba),
            "cena": float(cena),
            "kategoria_ID": int(kat_id)
        }
        supabase.table('Produkt').insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd zapisu produktu: {e}")
        return False

def aktualizuj_stan_db(prod_id, nowa_ilosc):
    """Aktualizuje tylko liczbę sztuk."""
    try:
        supabase.table('Produkt').update({"liczba": int(nowa_ilosc)}).eq("id", prod_id).execute()
        return True
    except Exception as e:
        st.error(f"Błąd aktualizacji stanu: {e}")
        return False

def usun_produkt_db(prod_id):
    """Usuwa produkt całkowicie."""
    try:
        supabase.table('Produkt').delete().eq("id", prod_id).execute()
        return True
    except Exception as e:
        st.error(f"Błąd usuwania produktu: {e}")
        return False

def dodaj_kategorie_db(nazwa, opis):
    try:
        supabase.table('kategorie').insert({"nazwa": nazwa, "opis": opis}).execute()
        return True
    except Exception as e:
        st.error(f"Błąd dodawania kategorii: {e}")
        return False

# --- 4. INTERFEJS UŻYTKOWNIKA ---

# Pobieramy dane na starcie
df, raw_data = pobierz_dane()

# --- SEKCJA STATYSTYK (PODSUMOWANIE) ---
st.markdown("### 📊 Podsumowanie")
col1, col2, col3 = st.columns(3)

suma_sztuk = 0
wartosc_magazynu = 0
liczba_pozycji = 0

if not df.empty and "Ilość" in df.columns:
    suma_sztuk = df["Ilość"].sum()
    wartosc_magazynu = sum(df["Ilość"] * df["Cena"])
    liczba_pozycji = len(df)

col1.metric("Łącznie sztuk towaru", f"{suma_sztuk} szt.")
col2.metric("Wartość magazynu", f"{wartosc_magazynu:.2f} PLN")
col3.metric("Różne produkty", f"{liczba_pozycji} poz.")

st.divider()

# --- ZAKŁADKI GŁÓWNE ---
tab_view, tab_add, tab_edit, tab_cat = st.tabs([
    "📋 Stan Magazynowy", 
    "➕ Przyjęcie Towaru (Dodaj)", 
    "📉 Wydanie / Usuwanie", 
    "🏷️ Zarządzaj Kategoriami"
])

# --- ZAKŁADKA 1: TABELA ---
with tab_view:
    st.subheader("Aktualny inwentarz")
    if not df.empty:
        st.dataframe(
            df,
            column_config={
                "Cena": st.column_config.NumberColumn(format="%.2f zł"),
                "Ilość": st.column_config.NumberColumn(format="%d szt."),
                "ID": st.column_config.NumberColumn(format="%d"),
                "Kategoria_ID": None # Ukrywamy ID kategorii w tabeli, bo mamy nazwę
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Brak danych lub magazyn jest pusty.")
    
    if st.button("🔄 Odśwież dane"):
        st.rerun()

# --- ZAKŁADKA 2: DODAWANIE PRODUKTU ---
with tab_add:
    st.subheader("Dodaj nowy produkt do bazy")
    
    cats = pobierz_liste_kategorii()
    if not cats:
        st.warning("⚠️ Brak kategorii! Dodaj je najpierw w zakładce 'Zarządzaj Kategoriami'.")
    else:
        mapa_kat = {c['nazwa']: c['id'] for c in cats}
        
        with st.form("add_product_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_nazwa = st.text_input("Nazwa produktu")
                new_kat = st.selectbox("Kategoria", list(mapa_kat.keys()))
            with col_b:
                new_ilosc = st.number_input("Ilość początkowa", min_value=1, step=1)
                new_cena = st.number_input("Cena (PLN)", min_value=0.01, step=0.01)
            
            submitted = st.form_submit_button("Zapisz w bazie")
            
            if submitted:
                if new_nazwa:
                    ok = dodaj_produkt_db(new_nazwa, new_ilosc, new_cena, mapa_kat[new_kat])
                    if ok:
                        st.success(f"Dodano: {new_nazwa}")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("Podaj nazwę produktu.")

# --- ZAKŁADKA 3: EDYCJA / USUWANIE / WYDANIE ---
with tab_edit:
    st.subheader("Operacje na produktach")
    
    if df.empty:
        st.info("Brak produktów do edycji.")
    else:
        # Tworzymy listę do selectboxa
        opcje_prod = {}
        for p in raw_data:
            # Zabezpieczenie na wypadek braku kluczy
            pid = p.get('ID')
            pnazwa = p.get('Nazwa')
            pilosc = p.get('Ilość')
            if pid is not None:
                label = f"{pnazwa} (ID: {pid} | Stan: {pilosc})"
                opcje_prod[label] = p

        if opcje_prod:
            wybrany_klucz = st.selectbox("Wybierz produkt:", list(opcje_prod.keys()))
            wybrany_produkt = opcje_prod[wybrany_klucz]
            
            current_id = wybrany_produkt['ID']
            current_ilosc = wybrany_produkt['Ilość']
            current_nazwa = wybrany_produkt['Nazwa']
            
            st.markdown(f"**Wybrano:** {current_nazwa} | **Aktualny stan:** {current_ilosc} szt.")
            st.write("---")
            
            col_edit, col_del = st.columns([2, 1])
            
            # Opcja A: Zmiana Ilości
            with col_edit:
                st.markdown("#### 📉 Wydanie / Aktualizacja stanu")
                nowa_ilosc_input = st.number_input(
                    "Nowy stan magazynowy", 
                    min_value=0, 
                    value=int(current_ilosc),
                    step=1,
                    key="edit_qty"
                )
                
                if st.button("Zatwierdź nową ilość"):
                    if nowa_ilosc_input != current_ilosc:
                        ok = aktualizuj_stan_db(current_id, nowa_ilosc_input)
                        if ok:
                            st.success(f"Zaktualizowano stan {current_nazwa}.")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("Ilość jest taka sama.")

            # Opcja B: Usuwanie
            with col_del:
                st.markdown("#### ❌ Usuń produkt")
                st.warning("Operacja nieodwracalna.")
                if st.button("Usuń z bazy"):
                    ok = usun_produkt_db(current_id)
                    if ok:
                        st.success(f"Usunięto {current_nazwa}.")
                        time.sleep(1)
                        st.rerun()
        else:
             st.warning("Coś poszło nie tak z listą produktów. Odśwież stronę.")

# --- ZAKŁADKA 4: KATEGORIE ---
with tab_cat:
    st.subheader("Zarządzanie Kategoriami")
    
    with st.form("add_cat_form"):
        c_nazwa = st.text_input("Nowa nazwa kategorii")
        c_opis = st.text_input("Opis (opcjonalnie)")
        sub_cat = st.form_submit_button("Dodaj kategorię")
        
        if sub_cat and c_nazwa:
            ok = dodaj_kategorie_db(c_nazwa, c_opis)
            if ok:
                st.success("Kategoria dodana.")
                time.sleep(0.5)
                st.rerun()
    
    cats_list = pobierz_liste_kategorii()
    if cats_list:
        st.write("Dostępne kategorie:")
        st.dataframe(pd.DataFrame(cats_list), hide_index=True)
