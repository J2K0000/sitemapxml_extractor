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
# Mots à ignorer lors de l'extraction depuis les URLs
COMMON_SLUG_WORDS = [
    'www', 'https', 'http', 'com', 'fr', 'org', 'net', 'html', 'php', 'aspx',
    'categorie', 'category', 'produit', 'product', 'page', 'post', 'article',
    'le', 'la', 'les', 'un', 'une', 'des', 'au', 'aux', 'du', 'de', 'et', 'ou'
]

def get_full_url(domain):
    """Assure que le domaine a un schéma (https:// par défaut)."""
    parsed = urlparse(domain)
    if not parsed.scheme:
        return 'https://' + domain.strip('/')
    return domain.strip('/')

def extract_keywords_from_url(url, collected_keywords):
    """Extrait des mots-clés pertinents du chemin d'une URL."""
    try:
        path = urlparse(url).path
        words = re.split(r'[/_-]', path)
        for word in words:
            cleaned_word = re.sub(r'\.\w+$', '', word).lower()
            if cleaned_word and cleaned_word not in COMMON_SLUG_WORDS and not cleaned_word.isdigit():
                collected_keywords.add(cleaned_word)
    except Exception:
        pass

def process_sitemap_content(content, sitemap_url, collected_keywords, collected_urls, visited_sitemaps):
    """Traite le contenu d'un sitemap, qu'il soit un index ou une liste d'URLs."""
    soup = BeautifulSoup(content, 'xml')

    sitemap_tags = soup.find_all('sitemap')
    if sitemap_tags:
        st.write(f"    ↪️ Index détecté. Analyse des sitemaps imbriqués...")
        for tag in sitemap_tags:
            nested_sitemap_url = tag.find('loc').text.strip()
            fetch_and_process_sitemap(nested_sitemap_url, collected_keywords, collected_urls, visited_sitemaps)
        return

    url_tags = soup.find_all('url')
    if url_tags:
        for tag in url_tags:
            page_url = tag.find('loc').text.strip()
            # Ajout de l'URL à la liste des URLs
            collected_urls.add(page_url)
            # Extraction des mots-clés depuis cette URL
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

st.title("🔎 Extracteur de Mots-clés & URLs via Sitemaps")
st.markdown("""
Cette application trouve les sitemaps d'un site, puis parcourt toutes les URLs listées pour extraire des mots-clés et générer une liste complète des URLs.
""")

domains_input = st.text_area(
    "Entrez un ou plusieurs noms de domaine (un par ligne)",
    "www.streamlit.io\nwww.lemonde.fr",
    height=80
)

if st.button("🚀 Lancer l'analyse", use_container_width=True, type="primary"):
    domains_list = [domain.strip() for domain in domains_input.split('\n') if domain.strip()]

    if not domains_list:
        st.warning("Veuillez entrer au moins un nom de domaine.")
    else:
        master_keywords_set = set()
        master_urls_set = set() # NOUVEAU: Set pour stocker toutes les URLs
        visited_sitemaps = set()
        
        progress_bar = st.progress(0, "Initialisation...")
        
        for i, domain in enumerate(domains_list):
            progress_text = f"Analyse de {domain} ({i+1}/{len(domains_list)})..."
            progress_bar.progress((i) / len(domains_list), text=progress_text)

            sitemaps_to_process = find_sitemaps_for_domain(domain)
            
            if sitemaps_to_process:
                st.write(f"**Processing {len(sitemaps_to_process)} sitemap(s) found...**")
                for sitemap_url in sitemaps_to_process:
                    fetch_and_process_sitemap(sitemap_url, master_keywords_set, master_urls_set, visited_sitemaps)

        progress_bar.progress(1.0, "Analyse terminée !")

        if not master_keywords_set and not master_urls_set:
            st.error("L'analyse est terminée, mais aucun mot-clé ou URL n'a pu être extrait.")
        else:
            st.balloons()
            st.success(f"🎉 Analyse terminée ! {len(master_keywords_set)} mots-clés uniques et {len(master_urls_set)} URLs uniques ont été trouvés.")
            
            # Créer des onglets pour les résultats
            tab1, tab2 = st.tabs(["🔑 Mots-clés", "🔗 URLs"])

            with tab1:
                st.subheader("Mots-clés Extraits")
                if master_keywords_set:
                    keywords_string = "\n".join(sorted(list(master_keywords_set)))
                    st.text_area("Aperçu des mots-clés", keywords_string, height=300, key="keywords_area")
                    st.download_button(
                        label="📥 Télécharger le fichier de mots-clés (.txt)",
                        data=keywords_string,
                        file_name="sitemap_keywords.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                else:
                    st.info("Aucun mot-clé n'a été extrait.")

            with tab2:
                st.subheader("URLs Extraites")
                if master_urls_set:
                    urls_string = "\n".join(sorted(list(master_urls_set)))
                    st.text_area("Aperçu des URLs", urls_string, height=300, key="urls_area")
                    st.download_button(
                        label="📥 Télécharger le fichier d'URLs (.txt)",
                        data=urls_string,
                        file_name="sitemap_urls.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                else:
                    st.info("Aucune URL n'a été extraite.")
