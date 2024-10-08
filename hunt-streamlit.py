import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re
import whois
import concurrent.futures
import pandas as pd

def search_keyword(keyword, num_results=5, ignore_websites=None):
    if ignore_websites is None:
        ignore_websites = {"go4worldbusiness","google.com", "maps", "quora", "tradeindia", "exportersindia", "alibaba", "reddit", "amazon", "wikipedia", "youtube", "thehindubusinessline", "pinterest", "indiamart","independent","packagingnews","justdial","ec21","hindustantimes"}
    
    search_url = f"https://www.google.com/search?q={keyword}&num={num_results}&start=0"
    try:
        websites = set()
        for page in range(0, 10):  # Limit to 5 pages
            response = requests.get(f"{search_url}&start={page*10}", headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a')
            
            for link in links:
                href = link.get('href')
                if href and "url?q=" in href:
                    full_url = href.split("url?q=")[1].split("&")[0]
                    base_url = urlparse(full_url).netloc
                    if base_url and not any(ignore in base_url for ignore in ignore_websites):
                        websites.add(base_url)
        
        filtered_websites = {website for website in websites if not website.endswith('.in')}
        return filtered_websites
    
    except requests.RequestException as e:
        st.error(f"Error retrieving search results: {e}")
        return set()

def find_contact_page(base_url):
    try:
        response = requests.get(f"http://{base_url}", headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        contact_pages = [link['href'] for link in links if 'contact' in link['href'].lower() or 'support' in link['href'].lower()]
        if contact_pages:
            return urljoin(f"http://{base_url}", contact_pages[0])
        return None
    except requests.RequestException as e:
        st.error(f"Error retrieving contact page for {base_url}: {e}")
        return None

def extract_emails_from_page(url, exclude_keywords=None):
    if exclude_keywords is None:
        exclude_keywords = ['careers', 'donations','press','media','feedback','communications','verifications','editor','research','india']
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        
        potential_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        
        cleaned_emails = set()
        for email in potential_emails:
            cleaned_email = re.sub(r'[^A-Za-z0-9._%+-]+$', '', email)
            if not any(keyword in cleaned_email for keyword in exclude_keywords):
                cleaned_emails.add(cleaned_email)
        
        return cleaned_emails
    except requests.RequestException as e:
        st.error(f"Request failed for URL {url}: {e}")
        return set()

def get_registration_country(domain):
    try:
        w = whois.whois(domain)
        country = w.get('country', 'Country information not available')
        return country if country else 'NA'
    except Exception as e:
        st.error(f"Error retrieving WHOIS information for {domain}: {e}")
        return 'Error'

def process_website(website):
    contact_page = find_contact_page(website)
    country = get_registration_country(website)
    
    if contact_page:
        emails = extract_emails_from_page(contact_page)
        if emails:
            return (website, country, emails if emails else "Nil")
    else:
        return (website, country, "Nil")
    
    return None

# Streamlit app
st.title('Email Extractor from Google based on the keyword search')

keywords_input = st.text_area("Enter the search keywords (one per line):", "Top IT companies in the world")
num_results = st.slider("Number of search results per keyword:", 1, 2, 5)

if st.button('Search'):
    if keywords_input:
        keywords = keywords_input.splitlines()
        all_results = []
        for keyword in keywords:
            with st.spinner(f"Searching for '{keyword}'... Please wait"):
                websites = search_keyword(keyword.strip(), num_results=num_results)
                if websites:
                    st.write(f"Number of unique websites found for '{keyword}': {len(websites)}")
                    results = []
                    email_count = 0
                    
                    # Initialize progress bar
                    progress_bar = st.empty()
                    total_websites = len(websites)
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        future_to_website = {executor.submit(process_website, website): website for website in websites}
                        for idx, future in enumerate(concurrent.futures.as_completed(future_to_website), start=1):
                            website = future_to_website[future]
                            try:
                                website_info = future.result()
                                if website_info:
                                    website, country, emails = website_info
                                    if emails == "Nil" or country == "CN":
                                        pass
                                    else:
                                        for email in emails:
                                            results.append([website, country, email])
                                            email_count += 1
                            except Exception as e:
                                st.error(f"An error occurred for website {website}: {e}")
                                results.append([website, "Error", "Error"])
                            
                            # Update progress bar with email count
                            progress_bar.progress(int((idx / total_websites) * 100))
                            progress_bar.text(f"Processed {idx}/{total_websites} websites, found {email_count} emails")
                    
                    # Collect results for all keywords
                    all_results.extend(results)
        
        if all_results:
            # Convert results to DataFrame
            df = pd.DataFrame(all_results, columns=["Website", "Country", "Email"])
            
            # Remove duplicates based on the "Email" column
            df.drop_duplicates(subset=["Email"], inplace=True)
            
            # Display the consolidated data
            st.dataframe(df)
            
            # Provide download options
            csv = df.to_csv(index=False)
            txt = df.to_string(index=False)
            
            st.download_button(
                label="Download as CSV",
                data=csv,
                file_name='website_info.csv',
                mime='text/csv'
            )
            
            st.download_button(
                label="Download as TXT",
                data=txt,
                file_name='website_info.txt',
                mime='text/plain'
            )
        else:
            st.write("No websites found or error occurred.")
# Add a footer with copyright information
st.markdown("---")
st.markdown("© 2024 Email Extractor. All rights reserved.")
st.markdown("Contact: [renuraj18@gmail.com](mailto:renuraj18@gmail.com)")
