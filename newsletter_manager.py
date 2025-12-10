import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from models import User, SearchHistory
from app import app, cerca_thomann, cerca_musik_produktiv, cerca_gear4music, cerca_andertons, cerca_strumentimusicali
from concurrent.futures import ThreadPoolExecutor

def send_weekly_newsletter():
    """
    Invia la newsletter settimanale agli utenti iscritti.
    Controlla le ultime ricerche e verifica se ci sono sconti.
    """
    print("Avvio invio newsletter...")
    
    with app.app_context():
        users = User.query.filter_by(newsletter_opt_in=True).all()
        
        for user in users:
            print(f"Elaborazione utente: {user.email}")
            
            # Prendi le ultime 5 ricerche uniche
            last_searches = SearchHistory.query.filter_by(user_id=user.id)\
                .order_by(SearchHistory.timestamp.desc())\
                .limit(20).all()
            
            unique_queries = []
            seen = set()
            for s in last_searches:
                if s.search_term not in seen:
                    unique_queries.append(s.search_term)
                    seen.add(s.search_term)
                if len(unique_queries) >= 5:
                    break
            
            if not unique_queries:
                print(f"Nessuna ricerca recente per {user.email}")
                continue
                
            # Cerca sconti per queste query
            discounted_products = []
            
            for query in unique_queries:
                print(f"  Controllo sconti per: {query}")
                # Esegui una ricerca rapida (limitata a pochi store per performance)
                # In produzione, questo dovrebbe essere fatto in background o con worker
                # Qui usiamo solo Thomann e StrumentiMusicali come esempio
                results = []
                try:
                    # Eseguiamo in sequenziale per non sovraccaricare
                    r1 = cerca_thomann(query)
                    if isinstance(r1, list): results.extend(r1)
                    
                    r2 = cerca_strumentimusicali(query)
                    if isinstance(r2, list): results.extend(r2)
                    
                except Exception as e:
                    print(f"  Errore ricerca {query}: {e}")
                
                # Filtra sconti
                for r in results:
                    try:
                        prezzo_attuale = float(str(r.get('prezzo', '0')).replace('€', '').replace('.', '').replace(',', '.').strip())
                        prezzo_originale = float(str(r.get('prezzo_originale_numerico', '0')).replace(',', '.').strip() or 0)
                        
                        if prezzo_originale > prezzo_attuale:
                            sconto = ((prezzo_originale - prezzo_attuale) / prezzo_originale) * 100
                            if sconto >= 10:  # Solo sconti rilevanti (>10%)
                                r['query_originale'] = query
                                r['sconto_percentuale'] = round(sconto)
                                discounted_products.append(r)
                    except:
                        continue
            
            # Se abbiamo trovato prodotti scontati, invia email
            if discounted_products:
                # Ordina per sconto decrescente e prendi i top 5
                discounted_products.sort(key=lambda x: x['sconto_percentuale'], reverse=True)
                top_products = discounted_products[:5]
                
                send_email(user.email, user.name, top_products)
            else:
                print(f"Nessun sconto rilevante trovato per {user.email}")

def send_email(to_email, name, products):
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv('EMAIL_SENDER')
        msg['To'] = to_email
        msg['Subject'] = '🎸 Sconti sui prodotti che cerchi!'

        html_content = f"""
        <html>
        <body>
            <h2>Ciao {name}, ecco alcuni sconti per te!</h2>
            <p>Basandoci sulle tue ultime ricerche, abbiamo trovato queste offerte:</p>
            <ul>
        """
        
        for p in products:
            html_content += f"""
            <li>
                <strong>{p.get('nome')}</strong><br>
                Prezzo: <span style="color: green; font-weight: bold;">{p.get('prezzo')}</span> 
                <span style="text-decoration: line-through; color: red;">(era {p.get('prezzo_originale', 'N/A')})</span><br>
                Sconto: <strong>{p.get('sconto_percentuale')}%</strong><br>
                <a href="{p.get('link')}">Vedi offerta su {p.get('sito', 'Store')}</a>
            </li>
            <br>
            """
            
        html_content += """
            </ul>
            <p>Buona musica,<br>Il team di Instrinder</p>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv('EMAIL_SENDER'), os.getenv('EMAIL_PASSWORD'))
        server.sendmail(msg['From'], msg['To'], msg.as_string())
        server.quit()
        
        print(f"✅ Email inviata a {to_email}")

    except Exception as e:
        print(f"❌ Errore invio email a {to_email}: {e}")

if __name__ == "__main__":
    send_weekly_newsletter()
