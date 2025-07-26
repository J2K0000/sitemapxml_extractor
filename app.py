import streamlit as st
import requests
import re
import os
import gzip
import io
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# --- Configuration de la page Streamlit ---
st.set_page_config(
    page_title="Sitemap Keyword & URL Extractor",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Constantes et Fonctions Utilitaires ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_full_url(domain):
    """Assure que le domaine a un schéma (https:// par défaut)."""
    parsed = urlparse(domain)
    if not parsed.scheme:
        return 'https://' + domain.strip('/')
    return domain.strip('/')

def extract_keywords_from_url(url, collected_keywords):
    """
    Extrait le dernier slug de l'URL comme mot-clé multi-mots.
    Exemple: pour ".../path/to/agence-seo", extrait "agence seo".
    """
    try:
        path = urlparse(url).path.strip('/')
        if not path:
            return

        last_slug = path.split('/')[-1]
        last_slug_no_ext = re.sub(r'\.\w+$', '', last_slug)
        keyword_phrase = re.sub(r'[-_]', ' ', last_slug_no_ext)

        if keyword_phrase and not keyword_phrase.isdigit():
            collected_keywords.add(keyword_phrase.lower())
            
    except Exception:
        pass

def process_sitemap_content(content, sitemap_url, collected_keywords, collected_urls, visited_sitemaps):
    """Traite le contenu d'un sitemap, qu'il soit un index ou une liste d'URLs."""
    try:
        soup = BeautifulSoup(content, 'lxml-xml')
    except Exception as e:
        st.warning(f"  ⚠️ Impossible d'analyser le contenu de {sitemap_url}. Erreur: {e}")
        return

    sitemap_tags = soup.find_all('sitemap')
    if sitemap_tags:
        st.write(f"    ↪️ Index détecté. Analyse de {len(sitemap_tags)} sitemaps imbriqués...")
        for tag in sitemap_tags:
            loc = tag.find('loc')
            if loc:
                nested_sitemap_url = loc.text.strip()
                fetch_and_process_sitemap(nested_sitemap_url, collected_keywords, collected_urls, visited_sitemaps)
        return

    url_tags = soup.find_all('url')
    if url_tags:
        for tag in url_tags:
            loc = tag.find('loc')
            if loc:
                page_url = loc.text.strip()
                collected_urls.add(page_url)
                extract_keywords_from_url(page_url, collected_keywords)

def fetch_and_process_sitemap(sitemap_url, collected_keywords, collected_urls, visited_sitemaps):
    """Télécharge et traite un sitemap, en gérant les doublons et les fichiers .gz."""
    if sitemap_url in visited_sitemaps:
        return
    visited_sitemaps.add(sitemap_url)

    st.write(f"  ↳ Téléchargement de {sitemap_url}...")
    try:
        response = requests.get(sitemap_url, headers=HEADERS, timeout=20)
        response.raise_for_status()

        content = response.content
        if sitemap_url.endswith('.gz'):
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz_file:
                uncompressed_content = gz_file.read()
            process_sitemap_content(uncompressed_content, sitemap_url, collected_keywords, collected_urls, visited_sitemaps)
        else:
            process_sitemap_content(content, sitemap_url, collected_keywords, collected_urls, visited_sitemaps)

    except requests.exceptions.RequestException as e:
        st.warning(f"  ⚠️ Impossible de télécharger {sitemap_url}. Erreur: {e}")

def find_sitemaps_for_domain(domain):
    """Cherche les sitemaps pour un domaine donné via robots.txt et les chemins courants."""
    st.subheader(f"Analyse de : {domain}")
    base_url = get_full_url(domain)
    found_sitemaps = set()

    st.write("1. Recherche dans `robots.txt`...")
    robots_url = urljoin(base_url, '/robots.txt')
    try:
        response = requests.get(robots_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            sitemap_urls = re.findall(r'^[Ss]itemap:\s*(.*)', response.text, re.MULTILINE)
            if sitemap_urls:
                st.write(f"  👍 Sitemaps trouvés dans `robots.txt`.")
                for url in sitemap_urls:
                    found_sitemaps.add(url.strip())
            else:
                st.write("  🤷 Aucun sitemap déclaré dans `robots.txt`.")
    except requests.exceptions.RequestException as e:
        st.warning(f"  ⚠️ Erreur lors de la récupération de `robots.txt`: {e}")

    if not found_sitemaps:
        st.write("2. Test des emplacements courants...")
        common_paths = ['/sitemap.xml', '/sitemap_index.xml', '/sitemap.xml.gz']
        for path in common_paths:
            test_url = urljoin(base_url, path)
            try:
                response = requests.head(test_url, headers=HEADERS, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    st.write(f"  👍 Sitemap potentiel trouvé à : {response.url}")
                    found_sitemaps.add(response.url)
                    break
            except requests.exceptions.RequestException:
                continue
    
    if not found_sitemaps:
        st.error("Aucun sitemap n'a pu être trouvé pour ce domaine.")

    return list(found_sitemaps)

# --- Interface Utilisateur Streamlit ---

st.title("🔎 Extracteur de Mots-clés & URLs par Domaine")
st.markdown("""
Cette application trouve les sitemaps d'un ou plusieurs sites, puis affiche les mots-clés et les URLs extraits **séparément pour chaque domaine**.
""")

domains_input = st.text_area(
    "Entrez un ou plusieurs noms de domaine (un par ligne)",
    "www.paulvengeons.fr\nwww.captaincontrat.com",
    height=80
)

if st.button("🚀 Lancer l'analyse", use_container_width=True, type="primary"):
    domains_list = [domain.strip() for domain in domains_input.split('\n') if domain.strip()]

    if not domains_list:
        st.warning("Veuillez entrer au moins un nom de domaine.")
    else:
        # MODIFICATION: Dictionnaire pour stocker les résultats par domaine
        all_results = {}
        visited_sitemaps = set()
        
        progress_bar = st.progress(0, "Initialisation...")
        
        with st.expander("Voir les logs d'analyse en direct", expanded=True):
            for i, domain in enumerate(domains_list):
                progress_text = f"Analyse de {domain} ({i+1}/{len(domains_list)})..."
                progress_bar.progress((i) / len(domains_list), text=progress_text)

                # Sets spécifiques pour ce domaine
                domain_keywords = set()
                domain_urls = set()

                sitemaps_to_process = find_sitemaps_for_domain(domain)
                
                if sitemaps_to_process:
                    st.write(f"**Traitement de {len(sitemaps_to_process)} sitemap(s) trouvé(s) pour {domain}...**")
                    for sitemap_url in sitemaps_to_process:
                        fetch_and_process_sitemap(sitemap_url, domain_keywords, domain_urls, visited_sitemaps)
                    
                    if domain_keywords or domain_urls:
                        # Stockage des résultats pour ce domaine
                        all_results[domain] = {
                            "keywords": domain_keywords,
                            "urls": domain_urls
                        }
                        st.success(f"-> {domain}: {len(domain_keywords)} mots-clés et {len(domain_urls)} URLs trouvés.")
                
                st.markdown("---")

        progress_bar.progress(1.0, "Analyse terminée !")

        if not all_results:
            st.error("L'analyse est terminée, mais aucun mot-clé ou URL n'a pu être extrait.")
        else:
            st.balloons()
            total_keywords = sum(len(data["keywords"]) for data in all_results.values())
            total_urls = sum(len(data["urls"]) for data in all_results.values())
            st.success(f"🎉 Analyse terminée ! {total_keywords} mots-clés et {total_urls} URLs trouvés au total sur {len(all_results)} domaine(s).")
            
            # MODIFICATION: Affichage des résultats par domaine dans des expanders
            for domain, data in all_results.items():
                with st.expander(f"⬇️ Résultats pour {domain} ({len(data['keywords'])} mots-clés, {len(data['urls'])} URLs)"):
                    
                    tab1, tab2 = st.tabs(["🔑 Mots-clés", "🔗 URLs"])
                    
                    sanitized_domain = re.sub(r'[^a-zA-Z0-9]', '_', domain)

                    with tab1:
                        st.subheader(f"Mots-clés pour {domain}")
                        if data["keywords"]:
                            keywords_string = "\n".join(sorted(list(data["keywords"])))
                            st.text_area("Aperçu des mots-clés", keywords_string, height=250, key=f"kw_area_{sanitized_domain}")
                            st.download_button(
                                label=f"📥 Télécharger les mots-clés pour {domain}",
                                data=keywords_string,
                                file_name=f"keywords_{sanitized_domain}.txt",
                                mime="text/plain",
                                use_container_width=True,
                                key=f"kw_btn_{sanitized_domain}"
                            )
                        else:
                            st.info("Aucun mot-clé n'a été extrait pour ce domaine.")

                    with tab2:
                        st.subheader(f"URLs pour {domain}")
                        if data["urls"]:
                            urls_string = "\n".join(sorted(list(data["urls"])))
                            st.text_area("Aperçu des URLs", urls_string, height=250, key=f"url_area_{sanitized_domain}")
                            st.download_button(
                                label=f"📥 Télécharger les URLs pour {domain}",
                                data=urls_string,
                                file_name=f"urls_{sanitized_domain}.txt",
                                mime="text/plain",
                                use_container_width=True,
                                key=f"url_btn_{sanitized_domain}"
                            )
                        else:
                            st.info("Aucune URL n'a été extraite pour ce domaine.")
