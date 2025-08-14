#!/usr/bin/env python3
"""
HotDoc Australia Doctor Information Scraper
============================================

This script scrapes comprehensive doctor information from HotDoc.com.au including:
- Doctor names and profiles
- Specializations and qualifications
- Clinic information and addresses
- Contact numbers
- Availability and booking information
- Reviews and ratings
- Medical center details

Author: AI Assistant
Date: August 2025
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import random
import re
import pandas as pd
from urllib.parse import urljoin, urlparse, parse_qs
from fake_useragent import UserAgent
import logging
from typing import Dict, List, Optional, Any
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hotdoc_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class HotDocScraper:
    """
    A comprehensive scraper for extracting doctor and medical center data from HotDoc.com.au
    """
    
    def __init__(self):
        self.base_url = "https://www.hotdoc.com.au"
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()
        self.scraped_data = []
        self.visited_urls = set()
        
    def setup_session(self):
        """Configure the session with headers and settings"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def get_page(self, url: str, max_retries: int = 3) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a web page with error handling and retries
        """
        for attempt in range(max_retries):
            try:
                # Random delay to avoid being blocked
                time.sleep(random.uniform(1, 3))
                
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                logging.info(f"Successfully fetched: {url}")
                return soup
                
            except requests.exceptions.RequestException as e:
                logging.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt == max_retries - 1:
                    logging.error(f"Failed to fetch {url} after {max_retries} attempts")
                    return None
                time.sleep(random.uniform(2, 5))
                
    def search_medical_centers(self, location: str = "", specialty: str = "", page: int = 1) -> List[str]:
        """
        Search for medical centers using HotDoc's actual search structure
        """
        center_urls = []
        
        try:
            # Try different search approaches
            search_urls = [
                f"{self.base_url}/search?filters=&in={location.replace(' ', '-').replace(',', '').lower()}",
                f"{self.base_url}/search?in={location.replace(' ', '-').replace(',', '').lower()}",
                f"{self.base_url}/medical-centres?location={location}",
            ]
            
            for search_url in search_urls:
                try:
                    response = self.session.get(search_url, timeout=30)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Look for medical center links in various formats
                    links = soup.find_all('a', href=True)
                    
                    for link in links:
                        href = link.get('href')
                        if href and '/medical-centres/' in href and '/doctors' in href:
                            full_url = urljoin(self.base_url, href)
                            if full_url not in self.visited_urls and full_url not in center_urls:
                                center_urls.append(full_url)
                    
                    if center_urls:
                        break
                        
                except Exception as e:
                    logging.warning(f"Search URL {search_url} failed: {str(e)}")
                    continue
            
            # If no results from search, try location-based URL construction
            if not center_urls and location:
                center_urls.extend(self.generate_location_urls(location))
            
            logging.info(f"Found {len(center_urls)} medical center URLs for {location}")
            return center_urls
            
        except Exception as e:
            logging.error(f"Error searching medical centers for {location}: {str(e)}")
            return []
    
    def generate_location_urls(self, location: str) -> List[str]:
        """
        Generate potential medical center URLs based on location patterns
        """
        urls = []
        
        try:
            # Parse location
            if ',' in location:
                suburb, state = location.split(',')
                suburb = suburb.strip().lower().replace(' ', '-')
                state = state.strip().upper()
                
                # Common postcode ranges for major cities
                postcode_ranges = {
                    'NSW': {'sydney': range(2000, 2250), 'newcastle': range(2300, 2320), 'wollongong': range(2500, 2530)},
                    'VIC': {'melbourne': range(3000, 3210), 'geelong': range(3220, 3230), 'ballarat': range(3350, 3360)},
                    'QLD': {'brisbane': range(4000, 4180), 'gold-coast': range(4210, 4230), 'townsville': range(4810, 4820)},
                    'WA': {'perth': range(6000, 6200), 'mandurah': range(6210, 6220)},
                    'SA': {'adelaide': range(5000, 5100)},
                    'TAS': {'hobart': range(7000, 7050)},
                    'ACT': {'canberra': range(2600, 2650)},
                    'NT': {'darwin': range(800, 850)}
                }
                
                # Try to find postcode range for this location
                if state in postcode_ranges:
                    for city_name, postcodes in postcode_ranges[state].items():
                        if city_name in suburb or suburb in city_name:
                            # Generate URLs for common postcodes in this area
                            for postcode in list(postcodes)[:10]:  # Limit to first 10 postcodes
                                url_location = f"{suburb}-{state}-{postcode}"
                                
                                # Try common clinic name patterns
                                common_patterns = [
                                    f"medical-centre",
                                    f"family-clinic", 
                                    f"health-centre",
                                    f"doctors",
                                    f"clinic",
                                    f"{suburb}-medical-centre",
                                    f"{suburb}-family-clinic",
                                    f"{suburb}-health-centre"
                                ]
                                
                                for pattern in common_patterns:
                                    test_url = f"{self.base_url}/medical-centres/{url_location}/{pattern}/doctors"
                                    urls.append(test_url)
                            
                            break
                
        except Exception as e:
            logging.error(f"Error generating location URLs: {str(e)}")
        
        return urls
    
    def extract_clinic_info(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        Extract clinic/medical center information from the page
        """
        clinic_info = {
            'clinic_name': None,
            'address': None,
            'suburb': None,
            'state': None,
            'postcode': None,
            'phone': None,
            'email': None,
            'website': None,
            'operating_hours': {},
            'services': [],
            'bulk_billing': None,
            'parking': None,
            'accessibility': None,
            'clinic_url': url
        }
        
        try:
            # Extract clinic name from title and other sources
            title_elem = soup.find('title')
            if title_elem:
                title_text = title_elem.get_text()
                # Extract clinic name from title like "Armadale Family Clinic - Book Doctors Online with HotDoc"
                if ' - ' in title_text:
                    clinic_info['clinic_name'] = title_text.split(' - ')[0].strip()
            
            # Try alternative selectors for clinic name
            if not clinic_info['clinic_name']:
                name_selectors = [
                    'h1.clinic-name',
                    'h1[data-testid="clinic-name"]',
                    '.clinic-header h1',
                    'h1.title',
                    '.clinic-title h1',
                    'h1'
                ]
                
                for selector in name_selectors:
                    name_elem = soup.select_one(selector)
                    if name_elem:
                        name_text = name_elem.get_text(strip=True)
                        if name_text and 'hotdoc' not in name_text.lower():
                            clinic_info['clinic_name'] = name_text
                            break
            
            # Extract address information from various sources
            # Check meta description first
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc:
                desc_content = meta_desc.get('content', '')
                # Extract address pattern like "Armadale, VIC 3143"
                address_match = re.search(r'([A-Za-z\s]+),\s*([A-Z]{2,3})\s*(\d{4})', desc_content)
                if address_match:
                    clinic_info['suburb'] = address_match.group(1).strip()
                    clinic_info['state'] = address_match.group(2).strip()
                    clinic_info['postcode'] = address_match.group(3).strip()
                    clinic_info['address'] = f"{clinic_info['suburb']}, {clinic_info['state']} {clinic_info['postcode']}"
            
            # Try to extract from URL if not found in meta
            if not clinic_info['address']:
                # Parse from URL pattern like /medical-centres/armadale-VIC-3143/
                url_match = re.search(r'/medical-centres/([^/]+)/([^/]+)', url)
                if url_match:
                    location_part = url_match.group(1)
                    # Parse location like "armadale-VIC-3143"
                    location_match = re.search(r'([^-]+)-([A-Z]{2,3})-(\d{4})', location_part)
                    if location_match:
                        clinic_info['suburb'] = location_match.group(1).replace('_', ' ').title()
                        clinic_info['state'] = location_match.group(2)
                        clinic_info['postcode'] = location_match.group(3)
                        clinic_info['address'] = f"{clinic_info['suburb']}, {clinic_info['state']} {clinic_info['postcode']}"
            
            # Look for detailed address in page content
            address_selectors = [
                '.clinic-address',
                '[data-testid="clinic-address"]',
                '.address-block',
                '.location-info .address',
                '.ClinicPage-Address',
                '.contact-address'
            ]
            
            for selector in address_selectors:
                address_elem = soup.select_one(selector)
                if address_elem:
                    address_text = address_elem.get_text(strip=True)
                    if address_text and len(address_text) > len(clinic_info.get('address', '')):
                        clinic_info['address'] = address_text
                        
                        # Parse detailed address components
                        address_parts = address_text.split(',')
                        if len(address_parts) >= 3:
                            clinic_info['suburb'] = address_parts[-3].strip()
                            state_postcode = address_parts[-2].strip().split()
                            if len(state_postcode) >= 2:
                                clinic_info['state'] = state_postcode[0]
                                clinic_info['postcode'] = state_postcode[1]
                    break
            
            # Extract phone number
            phone_selectors = [
                'a[href^="tel:"]',
                '.phone-number',
                '.contact-phone',
                '[data-testid="phone"]',
                '.ClinicPage-Phone'
            ]
            
            for selector in phone_selectors:
                phone_elem = soup.select_one(selector)
                if phone_elem:
                    if phone_elem.get('href'):
                        phone_text = phone_elem.get('href').replace('tel:', '')
                    else:
                        phone_text = phone_elem.get_text(strip=True)
                    
                    # Clean up phone number
                    phone_clean = re.sub(r'[^\d\+\(\)\s\-]', '', phone_text)
                    if phone_clean:
                        clinic_info['phone'] = phone_clean
                    break
            
            # Extract email
            email_selectors = [
                'a[href^="mailto:"]',
                '.email-address',
                '.contact-email'
            ]
            
            for selector in email_selectors:
                email_elem = soup.select_one(selector)
                if email_elem:
                    if email_elem.get('href'):
                        clinic_info['email'] = email_elem.get('href').replace('mailto:', '')
                    else:
                        clinic_info['email'] = email_elem.get_text(strip=True)
                    break
            
            # Extract services from page content
            service_keywords = [
                'general practice', 'family medicine', 'bulk billing', 'vaccination',
                'health check', 'women\'s health', 'men\'s health', 'child health',
                'chronic disease', 'mental health', 'skin checks', 'travel medicine',
                'sports medicine', 'pathology', 'radiology', 'physiotherapy'
            ]
            
            page_text = soup.get_text().lower()
            services = []
            for keyword in service_keywords:
                if keyword in page_text:
                    services.append(keyword.title())
            
            clinic_info['services'] = services
            
            # Extract bulk billing information
            bulk_billing_keywords = ['bulk bill', 'bulk billing', 'medicare']
            clinic_info['bulk_billing'] = any(keyword in page_text for keyword in bulk_billing_keywords)
            
        except Exception as e:
            logging.error(f"Error extracting clinic info: {str(e)}")
            
        return clinic_info
    
    def extract_doctor_info(self, soup: BeautifulSoup, clinic_info: Dict) -> List[Dict[str, Any]]:
        """
        Extract doctor information from the medical center page
        """
        doctors = []
        
        try:
            # HotDoc specific selectors for doctor availability rows
            doctor_selectors = [
                '.DoctorAvailabilityRow',
                '.doctor-card',
                '.practitioner-card',
                '.provider-card',
                '.doctor-profile',
                '[data-testid="doctor-card"]',
                '.practitioner-list .practitioner',
                '.doctor-item'
            ]
            
            doctor_elements = []
            for selector in doctor_selectors:
                elements = soup.select(selector)
                if elements:
                    doctor_elements = elements
                    logging.info(f"Found {len(elements)} doctor elements using selector: {selector}")
                    break
            
            if not doctor_elements:
                # Try alternative approach - look for doctor names in links
                doctor_links = soup.find_all('a', href=True)
                for link in doctor_links:
                    href = link.get('href', '')
                    if '/doctors/' in href and '/medical-centres/' in href:
                        # Find parent container
                        parent = link.parent
                        while parent and not parent.get('class'):
                            parent = parent.parent
                        if parent:
                            doctor_elements.append(parent)
            
            for doctor_elem in doctor_elements:
                doctor_info = self.extract_single_doctor_info(doctor_elem, clinic_info)
                if doctor_info and doctor_info.get('name'):
                    doctors.append(doctor_info)
            
            logging.info(f"Extracted information for {len(doctors)} doctors")
            
        except Exception as e:
            logging.error(f"Error extracting doctor info: {str(e)}")
            
        return doctors
    
    def extract_single_doctor_info(self, doctor_elem: BeautifulSoup, clinic_info: Dict) -> Dict[str, Any]:
        """
        Extract information for a single doctor
        """
        doctor_info = {
            'name': None,
            'title': None,
            'specialties': [],
            'qualifications': [],
            'experience_years': None,
            'languages': [],
            'gender': None,
            'bio': None,
            'rating': None,
            'review_count': None,
            'available_appointments': [],
            'consultation_types': [],
            'fees': {},
            'interests': [],
            'profile_url': None,
            'clinic_info': clinic_info
        }
        
        try:
            # Extract doctor name from HotDoc specific structure
            name_selectors = [
                '.DoctorAvailabilityRow-doctorLink',  # HotDoc specific
                '.DoctorAvailabilityRow-profileTitle a',  # HotDoc specific
                'h2 a',  # Generic fallback
                '.doctor-name',
                '.practitioner-name',
                '.provider-name',
                'h3', 'h4', 'h5',
                '.name',
                '[data-testid="doctor-name"]'
            ]
            
            for selector in name_selectors:
                name_elem = doctor_elem.select_one(selector)
                if name_elem:
                    name_text = name_elem.get_text(strip=True)
                    # Clean up name (remove titles like Dr., Prof., etc.)
                    doctor_info['name'] = self.clean_doctor_name(name_text)
                    doctor_info['title'] = self.extract_title(name_text)
                    
                    # Extract profile URL
                    if name_elem.name == 'a' and name_elem.get('href'):
                        doctor_info['profile_url'] = urljoin(self.base_url, name_elem.get('href'))
                    
                    break
            
            # Extract specialties and qualifications from HotDoc structure
            # Look for paragraph with qualifications and specialties
            info_paragraphs = doctor_elem.select('p')
            for p in info_paragraphs:
                text = p.get_text(strip=True)
                if text and any(keyword in text.lower() for keyword in ['practitioner', 'doctor', 'specialist']):
                    # Parse the info line like "General Practitioner, Female, FRACGP, MBBS, BMedSci"
                    parts = [part.strip() for part in text.split(',')]
                    
                    for part in parts:
                        part_lower = part.lower()
                        
                        # Check for gender
                        if part_lower in ['male', 'female']:
                            doctor_info['gender'] = part
                        
                        # Check for specialties
                        elif any(spec in part_lower for spec in ['practitioner', 'specialist', 'surgeon', 'consultant']):
                            if part not in doctor_info['specialties']:
                                doctor_info['specialties'].append(part)
                        
                        # Check for qualifications (usually all caps or mixed case with common medical degrees)
                        elif re.match(r'^[A-Z]{2,}', part) or any(qual in part.upper() for qual in ['MBBS', 'MD', 'FRACGP', 'FRACS', 'PHD', 'BMBS']):
                            if part not in doctor_info['qualifications']:
                                doctor_info['qualifications'].append(part)
                    
                    break
            
            # Extract languages
            for p in info_paragraphs:
                text = p.get_text(strip=True).lower()
                if 'speaks' in text or 'languages' in text:
                    # Extract languages after "Speaks"
                    lang_text = p.get_text(strip=True)
                    if 'speaks' in lang_text.lower():
                        langs = lang_text.lower().replace('speaks', '').strip()
                        # Handle common patterns like "English, Mandarin" or "English and Mandarin"
                        langs = re.sub(r'\s+and\s+', ', ', langs)
                        languages = [lang.strip().title() for lang in langs.split(',') if lang.strip()]
                        doctor_info['languages'] = languages
                    break
            
            # Extract bio from server-html div
            bio_elem = doctor_elem.select_one('.server-html p, .bio p, .description p')
            if bio_elem:
                doctor_info['bio'] = bio_elem.get_text(strip=True)
            
            # Extract interests from areas of interest section
            interests_section = doctor_elem.find('h4', string=re.compile(r'Areas of interest|Special interests|Clinical interests', re.I))
            if interests_section:
                # Look for list after the heading
                ul_elem = interests_section.find_next_sibling('ul')
                if ul_elem:
                    interests = []
                    for li in ul_elem.find_all('li'):
                        interest = li.get_text(strip=True)
                        if interest:
                            interests.append(interest)
                    doctor_info['interests'] = interests
            
            # Extract rating and reviews if available
            rating_elem = doctor_elem.select_one('.rating, .stars, [data-testid="rating"]')
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                if rating_match:
                    doctor_info['rating'] = float(rating_match.group(1))
            
            review_elem = doctor_elem.select_one('.review-count, .reviews')
            if review_elem:
                review_text = review_elem.get_text(strip=True)
                review_match = re.search(r'(\d+)', review_text)
                if review_match:
                    doctor_info['review_count'] = int(review_match.group(1))
            
        except Exception as e:
            logging.error(f"Error extracting single doctor info: {str(e)}")
            
        return doctor_info
    
    def get_detailed_doctor_info(self, profile_url: str) -> Dict[str, Any]:
        """
        Get detailed information from doctor's individual profile page
        """
        detailed_info = {}
        
        try:
            soup = self.get_page(profile_url)
            if not soup:
                return detailed_info
            
            # Extract bio/description
            bio_selectors = [
                '.doctor-bio',
                '.biography',
                '.description',
                '.about-doctor',
                '.profile-description'
            ]
            
            for selector in bio_selectors:
                bio_elem = soup.select_one(selector)
                if bio_elem:
                    detailed_info['bio'] = bio_elem.get_text(strip=True)
                    break
            
            # Extract languages
            lang_selectors = [
                '.languages',
                '.spoken-languages',
                '.language-list'
            ]
            
            languages = []
            for selector in lang_selectors:
                lang_elems = soup.select(f'{selector} li, {selector}')
                for elem in lang_elems:
                    lang = elem.get_text(strip=True)
                    if lang and lang not in languages:
                        languages.append(lang)
            
            detailed_info['languages'] = languages
            
            # Extract interests/special interests
            interest_selectors = [
                '.interests',
                '.special-interests',
                '.clinical-interests'
            ]
            
            interests = []
            for selector in interest_selectors:
                interest_elems = soup.select(f'{selector} li, {selector}')
                for elem in interest_elems:
                    interest = elem.get_text(strip=True)
                    if interest and interest not in interests:
                        interests.append(interest)
            
            detailed_info['interests'] = interests
            
            # Extract consultation types
            consult_selectors = [
                '.consultation-types',
                '.appointment-types',
                '.service-types'
            ]
            
            consultation_types = []
            for selector in consult_selectors:
                consult_elems = soup.select(f'{selector} li, {selector}')
                for elem in consult_elems:
                    consult_type = elem.get_text(strip=True)
                    if consult_type and consult_type not in consultation_types:
                        consultation_types.append(consult_type)
            
            detailed_info['consultation_types'] = consultation_types
            
        except Exception as e:
            logging.error(f"Error getting detailed doctor info from {profile_url}: {str(e)}")
            
        return detailed_info
    
    def clean_doctor_name(self, name_text: str) -> str:
        """
        Clean doctor name by removing titles and extra whitespace
        """
        # Remove common titles
        titles = ['dr', 'dr.', 'doctor', 'prof', 'prof.', 'professor', 'mr', 'ms', 'mrs', 'miss']
        words = name_text.split()
        cleaned_words = []
        
        for word in words:
            if word.lower().rstrip('.') not in titles:
                cleaned_words.append(word)
        
        return ' '.join(cleaned_words).strip()
    
    def extract_title(self, name_text: str) -> str:
        """
        Extract title from doctor's name
        """
        titles = ['dr', 'dr.', 'doctor', 'prof', 'prof.', 'professor']
        words = name_text.split()
        
        for word in words:
            if word.lower().rstrip('.') in titles:
                return word
        
        return 'Dr.'  # Default title
    
    def scrape_all_locations(self, locations: List[str] = None) -> None:
        """
        Scrape doctor data from multiple locations across Australia
        """
        if not locations:
            # Default major Australian cities and regions
            locations = [
                "Sydney, NSW", "Melbourne, VIC", "Brisbane, QLD", "Perth, WA",
                "Adelaide, SA", "Canberra, ACT", "Darwin, NT", "Hobart, TAS",
                "Gold Coast, QLD", "Newcastle, NSW", "Wollongong, NSW",
                "Geelong, VIC", "Townsville, QLD", "Cairns, QLD", "Ballarat, VIC",
                "Bendigo, VIC", "Mandurah, WA", "Mackay, QLD", "Rockhampton, QLD",
                "Bundaberg, QLD", "Coffs Harbour, NSW", "Wagga Wagga, NSW",
                "Shepparton, VIC", "Port Macquarie, NSW", "Tamworth, NSW"
            ]
        
        total_doctors = 0
        
        for location in locations:
            logging.info(f"Starting scrape for location: {location}")
            
            try:
                # First try search-based approach
                center_urls = self.search_medical_centers(location=location)
                
                # If search doesn't work, try alternative discovery methods
                if not center_urls:
                    center_urls = self.discover_medical_centers_alternative(location)
                
                processed_urls = 0
                successful_scrapes = 0
                
                for url in center_urls:
                    if url in self.visited_urls:
                        continue
                        
                    self.visited_urls.add(url)
                    processed_urls += 1
                    
                    # Check if URL exists before trying to scrape
                    if self.check_url_exists(url):
                        doctors_data = self.scrape_medical_center(url)
                        
                        if doctors_data:
                            self.scraped_data.extend(doctors_data)
                            total_doctors += len(doctors_data)
                            successful_scrapes += 1
                            logging.info(f"Total doctors scraped so far: {total_doctors}")
                            
                            # Save data periodically to avoid losing progress
                            if total_doctors % 100 == 0:
                                self.save_data(f"hotdoc_partial_{total_doctors}")
                                logging.info(f"Saved partial data at {total_doctors} doctors")
                
                logging.info(f"Location {location}: Processed {processed_urls} URLs, {successful_scrapes} successful scrapes")
                        
            except Exception as e:
                logging.error(f"Error scraping location {location}: {str(e)}")
                continue
        
        logging.info(f"Completed scraping. Total doctors: {total_doctors}")
    
    def discover_medical_centers_alternative(self, location: str) -> List[str]:
        """
        Alternative method to discover medical centers when search doesn't work
        """
        urls = []
        
        try:
            # Method 1: Try known medical center directories
            directory_urls = [
                f"{self.base_url}/medical-centres",
                f"{self.base_url}/health-services",
                f"{self.base_url}/clinics"
            ]
            
            for dir_url in directory_urls:
                try:
                    soup = self.get_page(dir_url)
                    if soup:
                        links = soup.find_all('a', href=True)
                        for link in links:
                            href = link.get('href')
                            if href and '/medical-centres/' in href and '/doctors' in href:
                                full_url = urljoin(self.base_url, href)
                                # Filter by location if possible
                                if self.url_matches_location(full_url, location):
                                    urls.append(full_url)
                except Exception as e:
                    logging.warning(f"Failed to check directory {dir_url}: {str(e)}")
            
            # Method 2: Generate URLs based on common patterns
            if not urls:
                urls.extend(self.generate_location_urls(location))
            
            # Method 3: Try to find through Google search (as fallback)
            if not urls:
                urls.extend(self.find_via_google_search(location))
                
        except Exception as e:
            logging.error(f"Error in alternative discovery for {location}: {str(e)}")
        
        return urls[:50]  # Limit to 50 URLs per location to avoid overwhelming
    
    def url_matches_location(self, url: str, location: str) -> bool:
        """
        Check if a URL matches the given location
        """
        try:
            if ',' in location:
                suburb, state = location.split(',')
                suburb = suburb.strip().lower().replace(' ', '-')
                state = state.strip().upper()
                
                url_lower = url.lower()
                return (suburb in url_lower and state.lower() in url_lower) or \
                       any(city in url_lower for city in [suburb, state.lower()])
        except:
            pass
        
        return True  # If we can't parse, include it anyway
    
    def check_url_exists(self, url: str) -> bool:
        """
        Check if a URL exists before trying to scrape it
        """
        try:
            response = self.session.head(url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def find_via_google_search(self, location: str) -> List[str]:
        """
        Find medical centers via Google search as last resort
        """
        urls = []
        
        try:
            # This is a fallback method - would need to implement Google search
            # For now, return empty list to avoid complications
            logging.info(f"Google search fallback not implemented for {location}")
        except Exception as e:
            logging.error(f"Google search failed: {str(e)}")
        
        return urls
    
    def scrape_medical_center(self, url: str) -> List[Dict[str, Any]]:
        """
        Scrape a single medical center for doctor information
        """
        try:
            soup = self.get_page(url)
            if not soup:
                return []
            
            # Extract clinic information
            clinic_info = self.extract_clinic_info(soup, url)
            
            # Extract doctor information
            doctors = self.extract_doctor_info(soup, clinic_info)
            
            logging.info(f"Scraped {len(doctors)} doctors from {clinic_info.get('clinic_name', 'Unknown Clinic')}")
            
            return doctors
            
        except Exception as e:
            logging.error(f"Error scraping medical center {url}: {str(e)}")
            return []
    
    def save_data(self, filename: str = None) -> None:
        """
        Save scraped data to JSON and CSV files
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hotdoc_doctors_{timestamp}"
        
        # Save to JSON
        json_filename = f"{filename}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(self.scraped_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Data saved to {json_filename}")
        
        # Save to CSV for easier analysis
        if self.scraped_data:
            try:
                # Flatten data for CSV
                flattened_data = []
                for doctor in self.scraped_data:
                    flat_doctor = {
                        'doctor_name': doctor.get('name'),
                        'title': doctor.get('title'),
                        'specialties': ', '.join(doctor.get('specialties', [])),
                        'qualifications': ', '.join(doctor.get('qualifications', [])),
                        'languages': ', '.join(doctor.get('languages', [])),
                        'rating': doctor.get('rating'),
                        'review_count': doctor.get('review_count'),
                        'bio': doctor.get('bio'),
                        'interests': ', '.join(doctor.get('interests', [])),
                        'consultation_types': ', '.join(doctor.get('consultation_types', [])),
                        'profile_url': doctor.get('profile_url'),
                        'clinic_name': doctor.get('clinic_info', {}).get('clinic_name'),
                        'clinic_address': doctor.get('clinic_info', {}).get('address'),
                        'clinic_suburb': doctor.get('clinic_info', {}).get('suburb'),
                        'clinic_state': doctor.get('clinic_info', {}).get('state'),
                        'clinic_postcode': doctor.get('clinic_info', {}).get('postcode'),
                        'clinic_phone': doctor.get('clinic_info', {}).get('phone'),
                        'clinic_email': doctor.get('clinic_info', {}).get('email'),
                        'clinic_services': ', '.join(doctor.get('clinic_info', {}).get('services', [])),
                        'bulk_billing': doctor.get('clinic_info', {}).get('bulk_billing'),
                        'clinic_url': doctor.get('clinic_info', {}).get('clinic_url')
                    }
                    flattened_data.append(flat_doctor)
                
                df = pd.DataFrame(flattened_data)
                csv_filename = f"{filename}.csv"
                df.to_csv(csv_filename, index=False, encoding='utf-8')
                
                logging.info(f"Data also saved to {csv_filename}")
                
            except Exception as e:
                logging.error(f"Error saving CSV file: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the scraped data
        """
        if not self.scraped_data:
            return {}
        
        stats = {
            'total_doctors': len(self.scraped_data),
            'total_clinics': len(set(d.get('clinic_info', {}).get('clinic_name') for d in self.scraped_data if d.get('clinic_info', {}).get('clinic_name'))),
            'states': {},
            'specialties': {},
            'doctors_with_ratings': 0,
            'average_rating': 0,
            'doctors_with_bios': 0
        }
        
        ratings = []
        
        for doctor in self.scraped_data:
            # Count by state
            state = doctor.get('clinic_info', {}).get('state')
            if state:
                stats['states'][state] = stats['states'].get(state, 0) + 1
            
            # Count specialties
            for specialty in doctor.get('specialties', []):
                stats['specialties'][specialty] = stats['specialties'].get(specialty, 0) + 1
            
            # Rating statistics
            if doctor.get('rating'):
                stats['doctors_with_ratings'] += 1
                ratings.append(doctor['rating'])
            
            # Bio statistics
            if doctor.get('bio'):
                stats['doctors_with_bios'] += 1
        
        if ratings:
            stats['average_rating'] = sum(ratings) / len(ratings)
        
        return stats


def main():
    """
    Main function to run the scraper
    """
    print("🏥 HotDoc Australia Doctor Information Scraper")
    print("=" * 50)
    
    scraper = HotDocScraper()
    
    # Get user preferences
    print("\nScraping Options:")
    print("1. Scrape all major Australian cities (comprehensive)")
    print("2. Scrape specific location")
    print("3. Scrape from a specific medical center URL")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        # Comprehensive scrape
        print("\n🚀 Starting comprehensive scrape of major Australian cities...")
        print("This may take several hours to complete.")
        confirm = input("Do you want to continue? (y/n): ").strip().lower()
        
        if confirm == 'y':
            scraper.scrape_all_locations()
        else:
            print("Scraping cancelled.")
            return
    
    elif choice == "2":
        # Specific location
        location = input("Enter location (e.g., 'Sydney, NSW', 'Melbourne, VIC'): ").strip()
        if location:
            print(f"\n🎯 Starting scrape for {location}...")
            scraper.scrape_all_locations([location])
        else:
            print("No location provided.")
            return
    
    elif choice == "3":
        # Specific URL
        url = input("Enter medical center URL: ").strip()
        if url:
            print(f"\n🎯 Scraping specific medical center: {url}")
            doctors_data = scraper.scrape_medical_center(url)
            scraper.scraped_data.extend(doctors_data)
        else:
            print("No URL provided.")
            return
    
    else:
        print("Invalid choice.")
        return
    
    # Save data
    if scraper.scraped_data:
        print(f"\n✅ Scraping completed! Found {len(scraper.scraped_data)} doctors.")
        scraper.save_data()
        
        # Display statistics
        stats = scraper.get_statistics()
        print("\n📊 Scraping Statistics:")
        print(f"Total Doctors: {stats.get('total_doctors', 0)}")
        print(f"Total Clinics: {stats.get('total_clinics', 0)}")
        print(f"Doctors with Ratings: {stats.get('doctors_with_ratings', 0)}")
        print(f"Average Rating: {stats.get('average_rating', 0):.2f}")
        print(f"Doctors with Bios: {stats.get('doctors_with_bios', 0)}")
        
        if stats.get('states'):
            print("\nDoctors by State:")
            for state, count in sorted(stats['states'].items()):
                print(f"  {state}: {count}")
        
        if stats.get('specialties'):
            print("\nTop 10 Specialties:")
            sorted_specialties = sorted(stats['specialties'].items(), key=lambda x: x[1], reverse=True)
            for specialty, count in sorted_specialties[:10]:
                print(f"  {specialty}: {count}")
    
    else:
        print("\n❌ No data was scraped. Please check the logs for errors.")


if __name__ == "__main__":
    main()