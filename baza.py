import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time

# --- 1. KONFIGURACJA STRONY ---
# Usunięto niestandardowe ikony i kolory. Ustawiono domyślny, czysty styl.
st.set_page_config(page_title="System WMS", layout="wide")

st.title("System WMS - Zarządzanie Magazynem")

# --- 2. POŁĄCZENIE Z BAZĄ DANYCH ---
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Błąd połączenia z bazą danych. Sprawdź plik secrets.toml.")
    st.stop()

# --- 3. FUNKCJE BAZY DANYCH (CRUD) ---

def pobierz_dane():
    try:
        response = supabase.table('Produkt').select("*, kategorie(nazwa)").execute()
        data = response.data
        cleaned_data = []
        for item in data:
            kat_nazwa = item.get('kategorie', {}).get('nazwa') if item.get('kategorie') else "Brak"
            # Obsługa różnych wielkości liter w kluczach
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
        st.error(f"Błąd pobierania danych: {e}")
        return pd.DataFrame(), []

def pobierz_liste_kategorii():
    res = supabase.table('kategorie').select("*").order('id').execute()
    return res.data

# --- PRODUKTY ---
def dodaj_produkt_db(nazwa, liczba, cena, kat_id):
    try:
        data = {"nazwa": nazwa, "liczba": int(liczba), "cena": float(cena), "kategoria_ID": int(kat_id)}
        supabase.table('Produkt').insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd: {e}")
        return False

def aktualizuj_stan_db(prod_id, nowa_ilosc):
    """Służy do szybkiej aktualizacji ilości (np. przy wysyłce)."""
    try:
        supabase.table('Produkt').update({"liczba": int(nowa_ilosc)}).eq("id", prod_id).execute()
        return True
    except Exception as e:
        st.error(f"Błąd aktualizacji stanu: {e}")
        return False

def edytuj_produkt_calosc(prod_id, nazwa, liczba, cena, kat_id):
    """Edytuje wszystkie pola produktu."""
    try:
        data = {"nazwa": nazwa, "liczba": int(liczba), "cena": float(cena), "kategoria_ID": int(kat_id)}
        supabase.table('Produkt').update(data).eq("id", prod_id).execute()
        return True
    except Exception as e:
        st.error(f"Błąd edycji: {e}")
        return False

def usun_produkt_db(prod_id):
    try:
        supabase.table('Produkt').delete().eq("id", prod_id).execute()
        return True
    except Exception as e:
        st.error(f"Błąd usuwania: {e}")
        return False

# --- KATEGORIE ---
def dodaj_kategorie_db(nazwa, opis):
    try:
        supabase.table('kategorie').insert({"nazwa": nazwa, "opis": opis}).execute()
        return True
    except Exception as e:
        st.error(f"Błąd: {e}")
        return False

def edytuj_kategorie_db(cat_id, nazwa, opis):
    try:
        supabase.table('kategorie').update({"nazwa": nazwa, "opis": opis}).eq("id", cat_id).execute()
        return True
    except Exception as e:
        st.error(f"Błąd edycji kategorii: {e}")
        return False

def usun_kategorie_db(cat_id):
    try:
        supabase.table('kategorie').delete().eq("id", cat_id).execute()
        return True
    except Exception as e:
        st.error("Nie można usunąć kategorii. Prawdopodobnie są do niej przypisane produkty.")
        return False

# --- 4. INTERFEJS UŻYTKOWNIKA ---

df, raw_data = pobierz_dane()
cats_list = pobierz_liste_kategorii()

# Mapowania pomocnicze
mapa_kat_id_nazwa = {c['id']: c['nazwa'] for c in cats_list} if cats_list else {}
mapa_kat_nazwa_id = {c['nazwa']: c['id'] for c in cats_list} if cats_list else {}

# --- PODSUMOWANIE (STATYSTYKI) ---
st.markdown("### Status Magazynu")
col1, col2, col3 = st.columns(3)
if not df.empty:
    col1.metric("Wszystkie sztuki", f"{df['Ilość'].sum()} szt.")
    col2.metric("Wartość", f"{sum(df['Ilość'] * df['Cena']):.2f} PLN")
    col3.metric("Rodzaje produktów", f"{len(df)}")
st.divider()

# --- ZAKŁADKI ---
# Teraz czyste nazwy bez emotek
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Stan Magazynowy", 
    "Dodaj Produkt", 
    "Wysyłka", 
    "Edycja Produktu", 
    "Kategorie"
])

# 1. LISTA
with tab1:
    st.subheader("Lista Produktów")
    if not df.empty:
        st.dataframe(
            df, 
            column_config={
                "Cena": st.column_config.NumberColumn(format="%.2f zł"),
                "Ilość": st.column_config.NumberColumn(format="%d szt."),
                "Kategoria_ID": None
            }, 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("Magazyn jest pusty.")
    
    if st.button("Odśwież tabelę"):
        st.rerun()

# 2. DODAJ PRODUKT
with tab2:
    st.subheader("Przyjęcie nowego towaru")
    if not cats_list:
        st.warning("Najpierw dodaj kategorie w zakładce 'Kategorie'!")
    else:
        with st.form("new_prod"):
            c1, c2 = st.columns(2)
            n_nazwa = c1.text_input("Nazwa")
            n_kat = c1.selectbox("Kategoria", list(mapa_kat_nazwa_id.keys()))
            n_ilosc = c2.number_input("Ilość", 1, step=1)
            n_cena = c2.number_input("Cena", 0.01, step=0.01)
            
            if st.form_submit_button("Dodaj do bazy"):
                if dodaj_produkt_db(n_nazwa, n_ilosc, n_cena, mapa_kat_nazwa_id[n_kat]):
                    st.success("Produkt dodany pomyślnie.")
                    time.sleep(1)
                    st.rerun()

# 3. WYSYŁKA (NOWA FUNKCJA)
with tab3:
    st.subheader("Wysyłka towaru")
    
    if df.empty:
        st.info("Brak produktów do wysyłki.")
    else:
        # Wybór produktu
        opcje = {f"{p['Nazwa']} (Dostępne: {p['Ilość']} szt.)": p for p in raw_data}
        wybor = st.selectbox("Wybierz produkt do wysłania", list(opcje.keys()))
        prod = opcje[wybor]
        
        dostepne = int(prod['Ilość'])
        
        with st.form("shipping_form"):
            st.write(f"Produkt: **{prod['Nazwa']}**")
            st.write(f"Stan magazynowy: {dostepne} szt.")
            
            ilosc_do_wyslania = st.number_input("Ile sztuk wysłać?", min_value=1, step=1)
            
            submit_ship = st.form_submit_button("Zatwierdź wysyłkę")
            
            if submit_ship:
                if ilosc_do_wyslania > dostepne:
                    st.error(f"Błąd: Nie masz tyle towaru! Dostępne tylko {dostepne} szt.")
                else:
                    nowy_stan = dostepne - ilosc_do_wyslania
                    if aktualizuj_stan_db(prod['ID'], nowy_stan):
                        st.success(f"Wysłano {ilosc_do_wyslania} szt. produktu {prod['Nazwa']}. Nowy stan: {nowy_stan}.")
                        time.sleep(1.5)
                        st.rerun()

# 4. EDYCJA / USUWANIE
with tab4:
    st.subheader("Edycja danych produktu")
    if not df.empty:
        opcje_edit = {f"{p['Nazwa']} (ID:{p['ID']})": p for p in raw_data}
        wybor_edit = st.selectbox("Wybierz produkt do edycji", list(opcje_edit.keys()), key="edit_select")
        prod_edit = opcje_edit[wybor_edit]
        
        with st.form("edit_prod_form"):
            col_e1, col_e2 = st.columns(2)
            
            e_nazwa = col_e1.text_input("Nazwa", value=prod_edit['Nazwa'])
            
            # Ustawienie domyślnej kategorii
            domyslny_index = 0
            if prod_edit['Kategoria_ID'] in mapa_kat_id_nazwa:
                biezaca_nazwa = mapa_kat_id_nazwa[prod_edit['Kategoria_ID']]
                if biezaca_nazwa in list(mapa_kat_nazwa_id.keys()):
                    domyslny_index = list(mapa_kat_nazwa_id.keys()).index(biezaca_nazwa)
            
            e_kat_nazwa = col_e1.selectbox("Kategoria", list(mapa_kat_nazwa_id.keys()), index=domyslny_index)
            
            # Tutaj można zrobić korektę stanu (np. inwentaryzacja)
            e_ilosc = col_e2.number_input("Ilość (Korekta stanu)", min_value=0, value=int(prod_edit['Ilość']))
            e_cena = col_e2.number_input("Cena (PLN)", min_value=0.01, value=float(prod_edit['Cena']))
            
            zapisz = st.form_submit_button("Zapisz zmiany")
            
            if zapisz:
                nowe_kat_id = mapa_kat_nazwa_id[e_kat_nazwa]
                if edytuj_produkt_calosc(prod_edit['ID'], e_nazwa, e_ilosc, e_cena, nowe_kat_id):
                    st.success("Dane produktu zaktualizowane.")
                    time.sleep(1)
                    st.rerun()
        
        st.divider()
        st.write("Usuwanie produktu")
        col_del, _ = st.columns([1, 4])
        if col_del.button("Usuń trwale ten produkt"):
            if usun_produkt_db(prod_edit['ID']):
                st.success("Produkt usunięty z bazy.")
                time.sleep(1)
                st.rerun()
    else:
        st.info("Brak produktów.")

# 5. KATEGORIE
with tab5:
    st.subheader("Zarządzanie Kategoriami")
    
    col_add_cat, col_edit_cat = st.columns(2)
    
    # A. Dodawanie
    with col_add_cat:
        st.write("Dodaj nową kategorię")
        with st.form("add_cat"):
            cn = st.text_input("Nazwa kategorii")
            co = st.text_input("Opis (opcjonalnie)")
            if st.form_submit_button("Dodaj"):
                if cn:
                    dodaj_kategorie_db(cn, co)
                    st.success("Kategoria dodana.")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Nazwa jest wymagana.")
    
    # B. Edycja / Usuwanie
    with col_edit_cat:
        st.write("Edytuj lub usuń kategorię")
        if cats_list:
            opcje_kat = {c['nazwa']: c for c in cats_list}
            wybor_kat = st.selectbox("Wybierz kategorię", list(opcje_kat.keys()))
            obj_kat = opcje_kat[wybor_kat]
            
            with st.form("edit_cat_form"):
                ec_nazwa = st.text_input("Edytuj nazwę", value=obj_kat['nazwa'])
                ec_opis = st.text_input("Edytuj opis", value=obj_kat['opis'] if obj_kat['opis'] else "")
                
                c_btn1, c_btn2 = st.columns(2)
                edycja = c_btn1.form_submit_button("Zapisz zmiany")
                usuniecie = c_btn2.form_submit_button("Usuń Kategorię")
                
                if edycja:
                    if edytuj_kategorie_db(obj_kat['id'], ec_nazwa, ec_opis):
                        st.success("Zaktualizowano kategorię.")
                        time.sleep(1)
                        st.rerun()
                
                if usuniecie:
                    if usun_kategorie_db(obj_kat['id']):
                        st.success("Usunięto kategorię.")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("Brak kategorii.")
