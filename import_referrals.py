"""
Script per importare link referral nel database.
Può essere utilizzato in modalità interattiva o per importare da un file CSV.
"""

import os
import csv
import json
import sys
from referral_db_manager import ReferralDBManager

def print_header():
    """Stampa l'intestazione dello script."""
    print("\n" + "="*60)
    print("IMPORTAZIONE LINK REFERRAL".center(60))
    print("="*60)
    print("\nQuesto script permette di importare link referral nel database.")
    print("I link possono essere importati manualmente o da un file CSV.")

def interactive_import():
    """Modalità interattiva per importare link referral uno alla volta."""
    print("\n--- MODALITÀ INTERATTIVA ---")
    print("Inserisci i dati del link referral (lascia vuoto per terminare):")
    
    while True:
        print("\nNuovo link referral:")
        original_url = input("URL originale: ").strip()
        if not original_url:
            break
            
        referral_url = input("URL referral: ").strip()
        if not referral_url:
            print("⚠️ URL referral mancante, inserimento annullato.")
            continue
            
        store_options = list(ReferralDBManager.DOMAIN_TO_STORE.values())
        print("\nStore disponibili:")
        for i, store in enumerate(store_options, 1):
            print(f"{i}. {store}")
            
        store_choice = input(f"Seleziona lo store (1-{len(store_options)}, o lascia vuoto per auto-detect): ").strip()
        
        store_name = None
        if store_choice and store_choice.isdigit():
            idx = int(store_choice) - 1
            if 0 <= idx < len(store_options):
                store_name = store_options[idx]
        
        # Se non è stato specificato lo store, prova a determinarlo dall'URL
        if not store_name:
            store_name = ReferralDBManager._get_store_from_url(original_url)
            if store_name:
                print(f"Store rilevato automaticamente: {store_name}")
            else:
                print("⚠️ Impossibile determinare lo store dall'URL.")
                store_name = input("Inserisci manualmente il nome dello store: ").strip()
        
        # Aggiungi il link al database
        if ReferralDBManager.add_referral_link(original_url, referral_url, store_name):
            print(f"✅ Link referral aggiunto con successo per {store_name}!")
        else:
            print("❌ Errore durante l'aggiunta del link referral.")
    
    print("\nImportazione interattiva terminata.")

def csv_import(file_path):
    """
    Importa link referral da un file CSV.
    
    Il file CSV deve avere le seguenti colonne:
    - original_url: URL originale del prodotto
    - referral_url: URL con referral
    - store (opzionale): Nome dello store
    """
    if not os.path.exists(file_path):
        print(f"❌ File non trovato: {file_path}")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            if not set(['original_url', 'referral_url']).issubset(set(reader.fieldnames)):
                print("❌ Il file CSV deve contenere almeno le colonne 'original_url' e 'referral_url'.")
                return
            
            referrals_data = []
            for row in reader:
                referrals_data.append({
                    'original_url': row.get('original_url', '').strip(),
                    'referral_url': row.get('referral_url', '').strip(),
                    'store': row.get('store', '').strip()
                })
            
            if not referrals_data:
                print("⚠️ Nessun dato trovato nel file CSV.")
                return
            
            count = ReferralDBManager.bulk_import_referrals(referrals_data)
            print(f"✅ Importazione completata: {count}/{len(referrals_data)} link referral importati.")
    
    except Exception as e:
        print(f"❌ Errore durante l'importazione dal file CSV: {str(e)}")

def export_template():
    """Crea un file CSV template per l'importazione dei link referral."""
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'referral_template.csv')
    
    try:
        with open(template_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['original_url', 'referral_url', 'store'])
            
            # Aggiungi alcune righe di esempio
            writer.writerow([
                'https://www.thomann.de/it/fender_stratocaster.htm',
                'https://www.thomann.de/it/fender_stratocaster.htm?partner_id=INSTRINDER123',
                'Thomann'
            ])
            writer.writerow([
                'https://www.andertons.co.uk/guitar-dept/electric-guitars/stratocaster/fender-player-stratocaster',
                'https://www.andertons.co.uk/guitar-dept/electric-guitars/stratocaster/fender-player-stratocaster?aff=INSTRINDER',
                'Andertons'
            ])
        
        print(f"✅ Template CSV creato: {template_path}")
        return template_path
    
    except Exception as e:
        print(f"❌ Errore durante la creazione del template CSV: {str(e)}")
        return None

def show_stats():
    """Mostra le statistiche del database dei referral."""
    print("\n--- STATISTICHE DATABASE REFERRAL ---")
    
    # Conta i referral per ogni store
    store_counts = {}
    for url, data in ReferralDBManager._referral_db.items():
        store = data.get('store', 'Sconosciuto')
        store_counts[store] = store_counts.get(store, 0) + 1
    
    print(f"Totale link referral nel database: {len(ReferralDBManager._referral_db)}")
    
    if store_counts:
        print("\nDistribuzione per store:")
        for store, count in sorted(store_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {store}: {count} link")
    
    # Mostra alcuni esempi di link nel database
    if ReferralDBManager._referral_db:
        print("\nEsempi di link nel database:")
        count = 0
        for original_url, data in ReferralDBManager._referral_db.items():
            if count >= 3:  # Mostra solo i primi 3 esempi
                break
            print(f"\n  {count+1}. Store: {data.get('store', 'Sconosciuto')}")
            print(f"     Original: {original_url}")
            print(f"     Referral: {data.get('referral_url', 'N/A')}")
            count += 1

def main():
    """Funzione principale dello script."""
    print_header()
    
    while True:
        print("\nOPZIONI:")
        print("1. Importazione interattiva (inserimento manuale)")
        print("2. Importazione da file CSV")
        print("3. Crea template CSV")
        print("4. Mostra statistiche database")
        print("0. Esci")
        
        choice = input("\nSeleziona un'opzione (0-4): ").strip()
        
        if choice == '0':
            print("\nChiusura dello script. Arrivederci!")
            break
            
        elif choice == '1':
            interactive_import()
            
        elif choice == '2':
            file_path = input("\nInserisci il percorso del file CSV: ").strip()
            if file_path:
                csv_import(file_path)
            
        elif choice == '3':
            template_path = export_template()
            if template_path:
                print(f"Puoi compilare il template e poi importarlo con l'opzione 2.")
            
        elif choice == '4':
            show_stats()
            
        else:
            print("⚠️ Opzione non valida. Riprova.")

if __name__ == "__main__":
    # Se vengono passati argomenti da riga di comando
    if len(sys.argv) > 1:
        if sys.argv[1] == '--csv' and len(sys.argv) > 2:
            csv_import(sys.argv[2])
        elif sys.argv[1] == '--template':
            export_template()
        elif sys.argv[1] == '--stats':
            show_stats()
        else:
            print("Utilizzo:")
            print("  python import_referrals.py                # Modalità interattiva")
            print("  python import_referrals.py --csv file.csv # Importa da CSV")
            print("  python import_referrals.py --template     # Crea template CSV")
            print("  python import_referrals.py --stats        # Mostra statistiche")
    else:
        main()
