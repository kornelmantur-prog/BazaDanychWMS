import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import time

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="System WMS Pro", layout="wide")
st.title("System WMS - Zarządzanie Magazynem")

# --- 2. POŁĄCZENIE Z BAZĄ DANYCH ---
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Błąd połączenia z bazą danych. Sprawdź plik secrets.toml.")
    st.stop()

# --- 3. FUNKCJE LOGIKI I BAZY DANYCH ---

# -- LOGI I HISTORIA --
def zapisz_historie(prod_nazwa, operacja, ilosc):
    try:
        supabase.table('historia_operacji').insert({
            "produkt_nazwa": prod_nazwa,
            "typ_operacji": operacja,
            "ilosc_zmiana": int(ilosc)
        }).execute()
    except Exception as e:
        print(f"Błąd logowania: {e}")

def pobierz_historie():
    try:
        res = supabase.table('historia_operacji').select("*").order("created_at", desc=True).limit(100).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        return pd.DataFrame()

# -- POBIERANIE DANYCH --
def pobierz_dane():
    try:
        response = supabase.table('Produkt').select("*, kategorie(nazwa)").execute()
        data = response.data
        cleaned_data = []
        for item in data:
            kat_nazwa = item.get('kategorie', {}).get('nazwa') if item.get('kategorie') else "Brak"
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

# -- OPERACJE NA PRODUKTACH --
def dodaj_produkt_db(nazwa, liczba, cena, kat_id):
    try:
        data = {"nazwa": nazwa, "liczba": int(liczba), "cena": float(cena), "kategoria_ID": int(kat_id)}
        supabase.table('Produkt').insert(data).execute()
        zapisz_historie(nazwa, "Nowy Produkt", liczba)
        return True
    except Exception as e:
        st.error(f"Błąd: {e}")
        return False

def aktualizuj_stan_db(prod_id, prod_nazwa, nowa_ilosc, stara_ilosc, typ_operacji="Korekta"):
    try:
        roznica = nowa_ilosc - stara_ilosc
        supabase.table('Produkt').update({"liczba": int(nowa_ilosc)}).eq("id", prod_id).execute()
        zapisz_historie(prod_nazwa, typ_operacji, roznica)
        return True
    except Exception as e:
        st.error(f"Błąd aktualizacji stanu: {e}")
        return False

def edytuj_produkt_calosc(prod_id, stara_nazwa, nowa_nazwa, liczba, cena, kat_id):
    try:
        data = {"nazwa": nowa_nazwa, "liczba": int(liczba), "cena": float(cena), "kategoria_ID": int(kat_id)}
        supabase.table('Produkt').update(data).eq("id", prod_id).execute()
        zapisz_historie(nowa_nazwa, "Edycja danych/stanu", liczba)
        return True
    except Exception as e:
        st.error(f"Błąd edycji: {e}")
        return False

def usun_produkt_db(prod_id, prod_nazwa):
    try:
        supabase.table('Produkt').delete().eq("id", prod_id).execute()
        zapisz_historie(prod_nazwa, "Usunięcie produktu", 0)
        return True
    except Exception as e:
        st.error(f"Błąd usuwania: {e}")
        return False

# -- KATEGORIE --
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

mapa_kat_id_nazwa = {c['id']: c['nazwa'] for c in cats_list} if cats_list else {}
mapa_kat_nazwa_id = {c['nazwa']: c['id'] for c in cats_list} if cats_list else {}

# --- DASHBOARD / STATYSTYKI ---
st.header("Panel Zarządzania")

# 1. Alerty
if not df.empty:
    low_stock = df[df["Ilość"] < 5]
    if not low_stock.empty:
        st.error(f"⚠️ Uwaga! {len(low_stock)} produktów ma niski stan (poniżej 5 szt.)")
    else:
        st.success("Stany magazynowe w normie.")

st.divider()

# 2. Metryki i Wykresy
col1, col2, col3 = st.columns(3)
if not df.empty:
    col1.metric("Wszystkie sztuki", f"{df['Ilość'].sum()} szt.")
    col2.metric("Wartość Magazynu", f"{sum(df['Ilość'] * df['Cena']):.2f} PLN")
    col3.metric("Ilość Produktów", f"{len(df)}")
    
    st.write("---")
    
    # --- WYKRESY KOŁOWE ---
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.subheader("Struktura Ilości (Sztuki)")
        qty_by_cat = df.groupby("Kategoria")["Ilość"].sum().reset_index()
        fig1 = px.pie(qty_by_cat, values='Ilość', names='Kategoria', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig1.update_traces(textinfo='value+label')
        st.plotly_chart(fig1, use_container_width=True)
        
    with chart_col2:
        st.subheader("Struktura Wartości (PLN)")
        df["Wartość Pozycji"] = df["Ilość"] * df["Cena"]
        val_by_cat = df.groupby("Kategoria")["Wartość Pozycji"].sum().reset_index()
        fig2 = px.pie(val_by_cat, values='Wartość Pozycji', names='Kategoria', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig2.update_traces(texttemplate='%{value:.2f} zł', textinfo='label+text')
        st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Dodaj produkty, aby zobaczyć statystyki.")

st.divider()

# --- ZAKŁADKI GŁÓWNE ---
# Dodano nową zakładkę w środku
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Stan Magazynowy", 
    "Dodaj Nowy Produkt", 
    "Dostawa (Uzupełnij)",  # <--- NOWA ZAKŁADKA
    "Wysyłka", 
    "Edycja Produktu", 
    "Kategorie",
    "Historia Operacji"
])

# 1. LISTA
with tab1:
    st.subheader("Lista Produktów")
    if not df.empty:
        st.dataframe(
            df[["Nazwa", "Ilość", "Cena", "Kategoria", "ID"]], 
            column_config={
                "Cena": st.column_config.NumberColumn(format="%.2f zł"),
                "Ilość": st.column_config.NumberColumn(format="%d szt."),
            }, 
            use_container_width=True, 
            hide_index=True
        )
    if st.button("Odśwież dane"):
        st.rerun()

# 2. DODAJ NOWY PRODUKT (TWORZENIE)
with tab2:
    st.subheader("Tworzenie nowego produktu")
    st.info("Tutaj dodajesz produkt, którego jeszcze nie ma w bazie.")
    if not cats_list:
        st.warning("Najpierw dodaj kategorie w zakładce 'Kategorie'!")
    else:
        with st.form("new_prod"):
            c1, c2 = st.columns(2)
            n_nazwa = c1.text_input("Nazwa")
            n_kat = c1.selectbox("Kategoria", list(mapa_kat_nazwa_id.keys()))
            n_ilosc = c2.number_input("Ilość początkowa", 1, step=1)
            n_cena = c2.number_input("Cena", 0.01, step=0.01)
            
            if st.form_submit_button("Dodaj do bazy"):
                if dodaj_produkt_db(n_nazwa, n_ilosc, n_cena, mapa_kat_nazwa_id[n_kat]):
                    st.success("Produkt dodany pomyślnie.")
                    time.sleep(1)
                    st.rerun()

# 3. DOSTAWA (NOWA ZAKŁADKA - UZUPEŁNIANIE)
with tab3:
    st.subheader("Przyjęcie dostawy (Uzupełnienie stanu)")
    st.info("Tutaj zwiększasz ilość produktu, który już istnieje.")
    
    if df.empty:
        st.info("Brak produktów w bazie.")
    else:
        opcje_dostawa = {f"{p['Nazwa']} (Obecnie: {p['Ilość']} szt.)": p for p in raw_data}
        wybor_dostawa = st.selectbox("Wybierz produkt z dostawy", list(opcje_dostawa.keys()), key="dostawa_select")
        prod_dostawa = opcje_dostawa[wybor_dostawa]
        obecny_stan = int(prod_dostawa['Ilość'])
        
        with st.form("restock_form"):
            st.write(f"Produkt: **{prod_dostawa['Nazwa']}**")
            st.write(f"Stan przed dostawą: {obecny_stan} szt.")
            
            ilosc_przyjeta = st.number_input("Ile sztuk przyjechało?", min_value=1, step=1, key="ilosc_przyjeta")
            
            if st.form_submit_button("Zaksięguj dostawę"):
                nowy_stan_lacznie = obecny_stan + ilosc_przyjeta
                if aktualizuj_stan_db(prod_dostawa['ID'], prod_dostawa['Nazwa'], nowy_stan_lacznie, obecny_stan, "Dostawa"):
                    st.success(f"Dodano {ilosc_przyjeta} szt. Nowy stan to: {nowy_stan_lacznie}.")
                    time.sleep(1)
                    st.rerun()

# 4. WYSYŁKA
with tab4:
    st.subheader("Wysyłka towaru")
    if df.empty:
        st.info("Brak produktów.")
    else:
        opcje = {f"{p['Nazwa']} (Dostępne: {p['Ilość']} szt.)": p for p in raw_data}
        wybor = st.selectbox("Wybierz produkt do wysłania", list(opcje.keys()), key="ship_select")
        prod = opcje[wybor]
        dostepne = int(prod['Ilość'])
        
        with st.form("shipping_form"):
            st.write(f"Wybrano: **{prod['Nazwa']}**")
            ilosc_do_wyslania = st.number_input("Ile sztuk wysłać?", min_value=1, step=1)
            
            if st.form_submit_button("Zatwierdź wysyłkę"):
                if ilosc_do_wyslania > dostepne:
                    st.error(f"Błąd: Nie masz tyle towaru! Dostępne: {dostepne}.")
                else:
                    nowy_stan = dostepne - ilosc_do_wyslania
                    if aktualizuj_stan_db(prod['ID'], prod['Nazwa'], nowy_stan, dostepne, "Wydanie"):
                        st.success(f"Wysłano {ilosc_do_wyslania} szt. Zaktualizowano stan.")
                        time.sleep(1)
                        st.rerun()

# 5. EDYCJA
with tab5:
    st.subheader("Edycja danych")
    if not df.empty:
        opcje_edit = {f"{p['Nazwa']} (ID:{p['ID']})": p for p in raw_data}
        wybor_edit = st.selectbox("Wybierz produkt do edycji", list(opcje_edit.keys()), key="edit_select")
        prod_edit = opcje_edit[wybor_edit]
        
        with st.form("edit_prod_form"):
            col_e1, col_e2 = st.columns(2)
            e_nazwa = col_e1.text_input("Nazwa", value=prod_edit['Nazwa'])
            
            domyslny_index = 0
            if prod_edit['Kategoria_ID'] in mapa_kat_id_nazwa:
                biezaca_nazwa = mapa_kat_id_nazwa[prod_edit['Kategoria_ID']]
                if biezaca_nazwa in list(mapa_kat_nazwa_id.keys()):
                    domyslny_index = list(mapa_kat_nazwa_id.keys()).index(biezaca_nazwa)
            
            e_kat_nazwa = col_e1.selectbox("Kategoria", list(mapa_kat_nazwa_id.keys()), index=domyslny_index)
            e_ilosc = col_e2.number_input("Ilość (Korekta ręczna)", min_value=0, value=int(prod_edit['Ilość']))
            e_cena = col_e2.number_input("Cena (PLN)", min_value=0.01, value=float(prod_edit['Cena']))
            
            if st.form_submit_button("Zapisz zmiany"):
                nowe_kat_id = mapa_kat_nazwa_id[e_kat_nazwa]
                if edytuj_produkt_calosc(prod_edit['ID'], prod_edit['Nazwa'], e_nazwa, e_ilosc, e_cena, nowe_kat_id):
                    st.success("Zapisano zmiany.")
                    time.sleep(1)
                    st.rerun()
        
        st.write("---")
        col_del, _ = st.columns([1, 4])
        if col_del.button("Usuń trwale ten produkt"):
            if usun_produkt_db(prod_edit['ID'], prod_edit['Nazwa']):
                st.success("Produkt usunięty.")
                time.sleep(1)
                st.rerun()

# 6. KATEGORIE
with tab6:
    st.subheader("Kategorie")
    col_add, col_list = st.columns(2)
    
    with col_add:
        with st.form("add_cat"):
            cn = st.text_input("Nazwa kategorii")
            co = st.text_input("Opis")
            if st.form_submit_button("Dodaj"):
                if cn:
                    dodaj_kategorie_db(cn, co)
                    st.success("Dodano.")
                    time.sleep(0.5)
                    st.rerun()
    
    with col_list:
        if cats_list:
            st.dataframe(pd.DataFrame(cats_list)[['nazwa', 'opis']], hide_index=True)
            st.write("Usuń kategorię:")
            k_to_del = st.selectbox("Wybierz do usunięcia", [c['nazwa'] for c in cats_list], key="del_cat_sel")
            id_to_del = mapa_kat_nazwa_id[k_to_del]
            if st.button("Usuń wybraną kategorię"):
                if usun_kategorie_db(id_to_del):
                    st.success("Usunięto.")
                    time.sleep(1)
                    st.rerun()

# 7. HISTORIA
with tab7:
    st.subheader("📜 Historia Operacji")
    df_hist = pobierz_historie()
    
    if not df_hist.empty:
        df_hist['created_at'] = pd.to_datetime(df_hist['created_at']).dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(
            df_hist[['created_at', 'produkt_nazwa', 'typ_operacji', 'ilosc_zmiana']],
            column_config={
                "created_at": "Data",
                "produkt_nazwa": "Produkt",
                "typ_operacji": "Działanie",
                "ilosc_zmiana": "Zmiana"
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Brak wpisów w historii.")
