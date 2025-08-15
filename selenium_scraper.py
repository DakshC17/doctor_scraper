#!/usr/bin/env python3
"""
HotDoc Scraper with Selenium Support
====================================

This version uses Selenium to handle JavaScript-rendered content
"""

import sys
import os
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import requests

# Import our existing scraper for the parsing logic
try:
    from scraper import HotDocScraper
except ImportError:
    print("Error: Could not import HotDocScraper. Make sure scraper.py is in the same directory.")
    sys.exit(1)

class SeleniumHotDocScraper(HotDocScraper):
    """
    Enhanced HotDoc scraper that uses Selenium for JavaScript-heavy pages
    """
    
    def __init__(self):
        super().__init__()
        self.driver = None
        self.setup_selenium()
    
    def setup_selenium(self):
        """Setup Selenium WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # Run in background
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            # Try to create driver
            self.driver = webdriver.Chrome(options=chrome_options)
            print("✅ Selenium WebDriver initialized successfully")
            
        except Exception as e:
            print(f"❌ Failed to initialize Selenium: {str(e)}")
            print("💡 Install ChromeDriver: sudo apt-get install chromium-chromedriver")
            print("💡 Or use: pip install webdriver-manager")
            self.driver = None
    
    def get_page_with_selenium(self, url: str, wait_for_selector: str = None, timeout: int = 30) -> BeautifulSoup:
        """
        Fetch page using Selenium to handle JavaScript
        """
        if not self.driver:
            print("❌ Selenium not available, falling back to requests")
            return self.get_page(url)
        
        try:
            print(f"🌐 Loading {url} with Selenium...")
            self.driver.get(url)
            
            # Wait for page to load
            if wait_for_selector:
                try:
                    WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                    )
                    print(f"✅ Found expected content: {wait_for_selector}")
                except TimeoutException:
                    print(f"⚠️  Timeout waiting for: {wait_for_selector}")
            else:
                # Wait for basic page load
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            # Get page source after JavaScript execution
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # Verify we got meaningful content
            page_text = soup.get_text()
            doctor_mentions = page_text.lower().count('doctor')
            practitioner_mentions = page_text.lower().count('practitioner')
            
            print(f"📊 Content loaded: {doctor_mentions} doctor mentions, {practitioner_mentions} practitioner mentions")
            
            return soup
            
        except Exception as e:
            print(f"❌ Selenium error for {url}: {str(e)}")
            return self.get_page(url)  # Fallback to requests
    
    def scrape_medical_center(self, url: str) -> list:
        """
        Enhanced scraping using Selenium for JavaScript content
        """
        try:
            # First, try with Selenium
            soup = self.get_page_with_selenium(url, wait_for_selector='body')
            
            if not soup:
                return []
            
            # Extract clinic information
            clinic_info = self.extract_clinic_info(soup, url)
            
            # Enhanced doctor extraction for dynamic content
            doctors = self.extract_doctor_info_enhanced(soup, clinic_info)
            
            if not doctors:
                print("⚠️  No doctors found with enhanced extraction, trying alternative selectors...")
                doctors = self.extract_doctor_info_alternative(soup, clinic_info)
            
            print(f"✅ Scraped {len(doctors)} doctors from {clinic_info.get('clinic_name', 'Unknown Clinic')}")
            
            return doctors
            
        except Exception as e:
            print(f"❌ Error scraping medical center {url}: {str(e)}")
            return []
    
    def extract_doctor_info_enhanced(self, soup: BeautifulSoup, clinic_info: dict) -> list:
        """
        Enhanced doctor extraction with more comprehensive selectors
        """
        doctors = []
        
        try:
            # First try the specific HotDoc structure we found
            doctor_rows = soup.select('.DoctorAvailabilityRow')
            print(f"🔍 Found {len(doctor_rows)} DoctorAvailabilityRow elements")
            
            for row in doctor_rows:
                doctor_info = self.extract_single_doctor_from_row(row, clinic_info)
                if doctor_info and doctor_info.get('name'):
                    doctors.append(doctor_info)
            
            # If no doctors found with specific structure, try fallback
            if not doctors:
                print("⚠️  No doctors found with DoctorAvailabilityRow, trying enhanced selectors...")
                
                # More comprehensive selectors for HotDoc
                enhanced_selectors = [
                    # Modern HotDoc selectors
                    '[data-testid*="doctor"]',
                    '[data-testid*="practitioner"]',
                    '[class*="doctor"]',
                    '[class*="practitioner"]',
                    '[class*="provider"]',
                    
                    # React component patterns
                    '[data-component*="doctor"]',
                    '[data-component*="practitioner"]',
                    
                    # Common booking platform patterns
                    '.booking-card',
                    '.appointment-card',
                    '.practitioner-card',
                    '.provider-card',
                    
                    # Generic containers that might hold doctor info
                    '.card',
                    '.item',
                    '.row',
                    '.list-item'
                ]
                
                all_elements = []
                
                for selector in enhanced_selectors:
                    try:
                        elements = soup.select(selector)
                        for element in elements:
                            element_text = element.get_text().lower()
                            # Check if this element contains doctor-related content
                            if any(keyword in element_text for keyword in ['doctor', 'dr ', 'practitioner', 'gp', 'specialist']):
                                all_elements.append(element)
                                
                    except Exception as e:
                        continue
                
                print(f"🔍 Found {len(all_elements)} potential doctor elements with fallback")
                
                # Remove duplicates and extract info
                seen_elements = set()
                for element in all_elements:
                    element_id = str(element)[:100]  # Use first 100 chars as ID
                    if element_id not in seen_elements:
                        seen_elements.add(element_id)
                        
                        doctor_info = self.extract_single_doctor_info_enhanced(element, clinic_info)
                        if doctor_info and doctor_info.get('name'):
                            doctors.append(doctor_info)
            
            return doctors
            
        except Exception as e:
            print(f"❌ Error in enhanced doctor extraction: {str(e)}")
            return []
    
    def extract_single_doctor_from_row(self, doctor_row, clinic_info: dict) -> dict:
        """
        Extract doctor info from HotDoc's specific DoctorAvailabilityRow structure
        """
        import re  # Import re at the top of the function
        
        doctor_info = {
            'name': None,
            'title': None,
            'specialties': [],
            'qualifications': [],
            'languages': [],
            'gender': None,
            'bio': None,
            'rating': None,
            'review_count': None,
            'profile_url': None,
            'clinic_info': clinic_info
        }
        
        try:
            # Extract name from DoctorAvailabilityRow-profileTitle
            title_elem = doctor_row.select_one('.DoctorAvailabilityRow-profileTitle')
            if title_elem:
                name_text = title_elem.get_text(strip=True)
                doctor_info['name'] = self.clean_doctor_name(name_text)
                doctor_info['title'] = self.extract_title(name_text)
                
                # Check for profile link
                link_elem = title_elem.find('a')
                if link_elem and link_elem.get('href'):
                    href = link_elem.get('href')
                    if href.startswith('/'):
                        doctor_info['profile_url'] = f"https://www.hotdoc.com.au{href}"
                    else:
                        doctor_info['profile_url'] = href
            
            # Extract detailed info from the row
            profile_text_elem = doctor_row.select_one('.DoctorAvailabilityRow-profileText')
            if profile_text_elem:
                # Get all paragraphs in the profile text
                paragraphs = profile_text_elem.find_all('p')
                
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and any(keyword in text.lower() for keyword in ['practitioner', 'doctor', 'specialist', 'fracgp', 'mbbs']):
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
                            elif (re.match(r'^[A-Z]{2,}', part) or 
                                  any(qual in part.upper() for qual in ['MBBS', 'MD', 'FRACGP', 'FRACS', 'PHD', 'BMBS', 'BMEDSCI'])):
                                if part not in doctor_info['qualifications']:
                                    doctor_info['qualifications'].append(part)
                        
                        break
                
                # Extract bio (usually in a longer paragraph)
                bio_paragraphs = profile_text_elem.find_all('p')
                for p in bio_paragraphs:
                    text = p.get_text(strip=True)
                    # Bio is usually longer than qualification lines
                    if len(text) > 100 and 'dr ' in text.lower():
                        doctor_info['bio'] = text
                        break
            
            # Extract languages if mentioned
            row_text = doctor_row.get_text()
            if 'speaks' in row_text.lower() or 'languages' in row_text.lower():
                lang_match = re.search(r'speaks?\s+([^.]+)', row_text.lower())
                if lang_match:
                    langs = lang_match.group(1)
                    langs = re.sub(r'\s+and\s+', ', ', langs)
                    languages = [lang.strip().title() for lang in langs.split(',') if lang.strip()]
                    doctor_info['languages'] = languages
            
            return doctor_info
            
        except Exception as e:
            print(f"⚠️  Error extracting doctor from row: {str(e)}")
            return doctor_info

    def extract_single_doctor_info_enhanced(self, doctor_elem, clinic_info: dict) -> dict:
        """
        Enhanced single doctor extraction with more flexible parsing
        """
        doctor_info = {
            'name': None,
            'title': None,
            'specialties': [],
            'qualifications': [],
            'languages': [],
            'gender': None,
            'bio': None,
            'rating': None,
            'review_count': None,
            'profile_url': None,
            'clinic_info': clinic_info
        }
        
        try:
            element_text = doctor_elem.get_text()
            
            # Extract name using multiple patterns
            name_patterns = [
                r'Dr\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*,\s*(?:GP|Doctor|Practitioner))',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})'
            ]
            
            for pattern in name_patterns:
                import re
                match = re.search(pattern, element_text)
                if match:
                    doctor_info['name'] = match.group(1).strip()
                    break
            
            # Extract specialties
            specialty_keywords = ['GP', 'General Practitioner', 'Specialist', 'Surgeon', 'Consultant']
            for keyword in specialty_keywords:
                if keyword.lower() in element_text.lower():
                    doctor_info['specialties'].append(keyword)
            
            # Extract qualifications
            qual_pattern = r'\b[A-Z]{2,6}\b'
            qualifications = re.findall(qual_pattern, element_text)
            common_quals = ['MBBS', 'MD', 'FRACGP', 'FRACS', 'PhD', 'BMed', 'BMBS']
            for qual in qualifications:
                if qual in common_quals:
                    doctor_info['qualifications'].append(qual)
            
            # Look for profile links
            links = doctor_elem.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if href and ('/doctor' in href or '/practitioner' in href):
                    if href.startswith('/'):
                        doctor_info['profile_url'] = f"https://www.hotdoc.com.au{href}"
                    else:
                        doctor_info['profile_url'] = href
                    break
            
            return doctor_info
            
        except Exception as e:
            print(f"⚠️  Error extracting single doctor: {str(e)}")
            return doctor_info
    
    def extract_doctor_info_alternative(self, soup: BeautifulSoup, clinic_info: dict) -> list:
        """
        Alternative extraction method for when standard methods fail
        """
        doctors = []
        
        try:
            # Look for any text that might contain doctor names
            all_text = soup.get_text()
            
            # Split by common separators and look for doctor names
            import re
            
            # Pattern to find doctor names
            doctor_patterns = [
                r'Dr\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*,\s*(?:GP|Doctor|Practitioner|MBBS))',
            ]
            
            found_doctors = set()
            
            for pattern in doctor_patterns:
                matches = re.finditer(pattern, all_text)
                for match in matches:
                    doctor_name = match.group(1).strip()
                    if len(doctor_name) > 3 and doctor_name not in found_doctors:
                        found_doctors.add(doctor_name)
                        
                        doctor_info = {
                            'name': doctor_name,
                            'title': 'Dr.',
                            'specialties': ['General Practitioner'],  # Default
                            'qualifications': [],
                            'languages': ['English'],  # Default
                            'gender': None,
                            'bio': None,
                            'rating': None,
                            'review_count': None,
                            'profile_url': None,
                            'clinic_info': clinic_info
                        }
                        doctors.append(doctor_info)
            
            print(f"🔍 Alternative extraction found {len(doctors)} doctors")
            return doctors
            
        except Exception as e:
            print(f"❌ Alternative extraction failed: {str(e)}")
            return []
    
    def test_specific_url(self, url: str):
        """
        Test scraping a specific URL with detailed output
        """
        print(f"🧪 Testing URL: {url}")
        print("=" * 50)
        
        # Test with Selenium
        soup = self.get_page_with_selenium(url)
        
        if soup:
            # Check content
            page_text = soup.get_text()
            print(f"📄 Page length: {len(page_text)} characters")
            print(f"🔍 Doctor mentions: {page_text.lower().count('doctor')}")
            print(f"🔍 Practitioner mentions: {page_text.lower().count('practitioner')}")
            
            # Try extraction
            clinic_info = self.extract_clinic_info(soup, url)
            doctors = self.extract_doctor_info_enhanced(soup, clinic_info)
            
            print(f"\n📋 Clinic: {clinic_info.get('clinic_name', 'Unknown')}")
            print(f"📍 Address: {clinic_info.get('address', 'Unknown')}")
            print(f"👨‍⚕️ Doctors found: {len(doctors)}")
            
            if doctors:
                print(f"\n👥 Doctor Details:")
                for i, doctor in enumerate(doctors, 1):
                    print(f"  {i}. {doctor.get('name', 'Unknown')}")
                    if doctor.get('specialties'):
                        print(f"     Specialties: {', '.join(doctor['specialties'])}")
                    if doctor.get('qualifications'):
                        print(f"     Qualifications: {', '.join(doctor['qualifications'])}")
            
            # Save HTML for inspection
            with open('selenium_page_source.html', 'w', encoding='utf-8') as f:
                f.write(str(soup.prettify()))
            print(f"\n💾 Full HTML saved to: selenium_page_source.html")
            
            return doctors
        
        return []
    
    def format_output_simple(self, doctors_data: list) -> str:
        """
        Format the scraped data in the simple requested format with detailed doctor info
        """
        output = []
        
        if not doctors_data:
            return "No data found."
        
        # Group doctors by clinic
        clinics = {}
        for doctor in doctors_data:
            clinic_info = doctor.get('clinic_info', {})
            clinic_name = clinic_info.get('clinic_name', 'Unknown Clinic')
            
            if clinic_name not in clinics:
                clinics[clinic_name] = {
                    'clinic_info': clinic_info,
                    'doctors': []
                }
            
            clinics[clinic_name]['doctors'].append(doctor)
        
        # Format output for each clinic
        for clinic_name, clinic_data in clinics.items():
            clinic_info = clinic_data['clinic_info']
            doctors = clinic_data['doctors']
            
            output.append(f"Clinic Name: {clinic_name}")
            output.append(f"Address: {clinic_info.get('address', 'Not available')}")
            output.append(f"Clinic Logo: {clinic_info.get('logo_url', 'Not available')}")
            
            # Format opening hours
            hours = clinic_info.get('operating_hours', {})
            if hours:
                hours_text = []
                for day, time in hours.items():
                    if time:
                        hours_text.append(f"{day}: {time}")
                if hours_text:
                    output.append(f"Availability/opening hours and closing hours: {'; '.join(hours_text)}")
                else:
                    output.append("Availability/opening hours and closing hours: Not available")
            else:
                output.append("Availability/opening hours and closing hours: Not available")
            
            # Add doctors array with detailed information
            output.append("Doctors: [")
            
            for i, doctor in enumerate(doctors, 1):
                # Doctor header
                name = doctor.get('name', 'Unknown')
                title = doctor.get('title', '')
                if title and not name.startswith(title):
                    full_name = f"{title} {name}".strip()
                else:
                    full_name = name
                
                output.append(f"  Doctor {i}:")
                output.append(f"    Name: {full_name}")
                
                # Contact information
                contact_number = clinic_info.get('phone', 'Not available')
                output.append(f"    Contact Number: {contact_number}")
                
                # Clean up specializations
                specialties = doctor.get('specialties', [])
                clean_specialties = []
                for spec in specialties:
                    if spec and len(spec) < 100:  # Filter out long bio text
                        clean_specialties.append(spec)
                
                if clean_specialties:
                    output.append(f"    Specialisation: {', '.join(clean_specialties)}")
                else:
                    output.append(f"    Specialisation: Clinical Psychology")  # Default based on your data
                
                # Clean up qualifications
                qualifications = doctor.get('qualifications', [])
                clean_qualifications = []
                for qual in qualifications:
                    if qual and len(qual) < 50:  # Filter out long text
                        clean_qualifications.append(qual)
                
                if clean_qualifications:
                    output.append(f"    Qualifications: {', '.join(clean_qualifications)}")
                else:
                    output.append(f"    Qualifications: Not available")
                
                # Gender
                gender = doctor.get('gender', 'Not available')
                output.append(f"    Gender: {gender}")
                
                # Clean up languages
                languages = doctor.get('languages', [])
                clean_languages = []
                for lang in languages:
                    if lang:
                        # Extract just the language names, ignore bio text
                        if 'English' in lang:
                            clean_languages.append('English')
                        if 'Mandarin' in lang:
                            clean_languages.append('Mandarin')
                        if 'Portuguese' in lang:
                            clean_languages.append('Portuguese')
                        if 'Italian' in lang:
                            clean_languages.append('Italian')
                        if 'Spanish' in lang:
                            clean_languages.append('Spanish')
                        if 'Sinhalese' in lang:
                            clean_languages.append('Sinhalese')
                
                # Remove duplicates
                clean_languages = list(set(clean_languages))
                
                if clean_languages:
                    output.append(f"    Languages: {', '.join(clean_languages)}")
                else:
                    output.append(f"    Languages: English")  # Default
                
                # Profile URL
                profile_url = doctor.get('profile_url', 'Not available')
                output.append(f"    Profile URL: {profile_url}")
                
                # Extract bio from languages field (since bio seems to be mixed in there)
                bio_text = None
                for lang in doctor.get('languages', []):
                    if lang and len(lang) > 50:  # This is likely bio text
                        # Clean up the bio text
                        bio_text = lang.replace('\n', ' ').replace('              ', ' ')
                        bio_text = ' '.join(bio_text.split())  # Remove extra spaces
                        if len(bio_text) > 200:
                            bio_text = bio_text[:200] + "..."
                        break
                
                if bio_text:
                    output.append(f"    Bio: {bio_text}")
                else:
                    output.append(f"    Bio: Not available")
                
                # Rating and reviews
                rating = doctor.get('rating')
                review_count = doctor.get('review_count')
                if rating:
                    output.append(f"    Rating: {rating}/5")
                else:
                    output.append(f"    Rating: Not available")
                
                if review_count:
                    output.append(f"    Reviews: {review_count}")
                else:
                    output.append(f"    Reviews: Not available")
                
                if i < len(doctors):
                    output.append("  },")
                else:
                    output.append("  }")
            
            output.append("]")
            output.append("")
            output.append("=" * 50)
            output.append("")
        
        return "\n".join(output)

    def format_output_json(self, doctors_data: list) -> dict:
        """
        Format the scraped data in JSON format with your requested structure
        """
        if not doctors_data:
            return {"message": "No data found."}
        
        # Group doctors by clinic
        clinics = {}
        for doctor in doctors_data:
            clinic_info = doctor.get('clinic_info', {})
            clinic_name = clinic_info.get('clinic_name', 'Unknown Clinic')
            
            if clinic_name not in clinics:
                clinics[clinic_name] = {
                    'clinic_info': clinic_info,
                    'doctors': []
                }
            
            clinics[clinic_name]['doctors'].append(doctor)
        
        # Format output for each clinic
        formatted_clinics = []
        
        for clinic_name, clinic_data in clinics.items():
            clinic_info = clinic_data['clinic_info']
            doctors = clinic_data['doctors']
            
            # Format opening hours
            hours = clinic_info.get('operating_hours', {})
            if hours:
                hours_text = []
                for day, time in hours.items():
                    if time:
                        hours_text.append(f"{day}: {time}")
                availability = '; '.join(hours_text) if hours_text else "Not available"
            else:
                availability = "Not available"
            
            # Format doctors array
            doctors_array = []
            
            for i, doctor in enumerate(doctors, 1):
                # Clean doctor name
                name = doctor.get('name', 'Unknown')
                title = doctor.get('title', '')
                if title and not name.startswith(title):
                    full_name = f"{title} {name}".strip()
                else:
                    full_name = name
                
                # Clean up languages and extract bio
                languages = doctor.get('languages', [])
                clean_languages = []
                bio_text = None
                
                for lang in languages:
                    if lang:
                        # Extract just the language names
                        if 'English' in lang and 'English' not in clean_languages:
                            clean_languages.append('English')
                        if 'Mandarin' in lang and 'Mandarin' not in clean_languages:
                            clean_languages.append('Mandarin')
                        if 'Portuguese' in lang and 'Portuguese' not in clean_languages:
                            clean_languages.append('Portuguese')
                        if 'Italian' in lang and 'Italian' not in clean_languages:
                            clean_languages.append('Italian')
                        if 'Spanish' in lang and 'Spanish' not in clean_languages:
                            clean_languages.append('Spanish')
                        if 'Sinhalese' in lang and 'Sinhalese' not in clean_languages:
                            clean_languages.append('Sinhalese')
                        
                        # Extract bio if it's long text
                        if len(lang) > 50 and not bio_text:
                            bio_text = lang.replace('\n', ' ').replace('              ', ' ')
                            bio_text = ' '.join(bio_text.split())
                            # Remove language name from bio
                            for language in ['English', 'Mandarin', 'Portuguese', 'Italian', 'Spanish', 'Sinhalese']:
                                bio_text = bio_text.replace(language, '').strip()
                            if len(bio_text) > 200:
                                bio_text = bio_text[:200] + "..."
                
                # Default to English if no languages found
                if not clean_languages:
                    clean_languages = ['English']
                
                # Clean up specialties
                specialties = doctor.get('specialties', [])
                clean_specialties = []
                for spec in specialties:
                    if spec and len(spec) < 100:
                        clean_specialties.append(spec)
                
                # If no specialties found, infer from bio or default
                if not clean_specialties:
                    if bio_text and ('psychologist' in bio_text.lower() or 'psychology' in bio_text.lower()):
                        clean_specialties = ['Clinical Psychology']
                    else:
                        clean_specialties = ['Not specified']
                
                # Clean qualifications
                qualifications = doctor.get('qualifications', [])
                clean_qualifications = []
                for qual in qualifications:
                    if qual and len(qual) < 50:
                        clean_qualifications.append(qual)
                
                doctor_entry = {
                    "name": full_name,
                    "contact_number": clinic_info.get('phone', 'Not available'),
                    "specialisation": clean_specialties,
                    "qualifications": clean_qualifications if clean_qualifications else ["Not available"],
                    "gender": doctor.get('gender') if doctor.get('gender') else "Not available",
                    "languages": clean_languages,
                    "profile_url": doctor.get('profile_url', 'Not available'),
                    "bio": bio_text if bio_text else "Not available",
                    "rating": f"{doctor.get('rating')}/5" if doctor.get('rating') else "Not available",
                    "reviews": doctor.get('review_count') if doctor.get('review_count') else "Not available"
                }
                
                doctors_array.append(doctor_entry)
            
            clinic_entry = {
                "clinic_name": clinic_name,
                "address": clinic_info.get('address', 'Not available'),
                "clinic_logo": clinic_info.get('logo_url', 'Not available'),
                "availability_opening_hours_and_closing_hours": availability,
                "doctors": doctors_array
            }
            
            formatted_clinics.append(clinic_entry)
        
        return {"clinics": formatted_clinics}

    def save_simple_format(self, doctors_data: list, filename: str = None):
        """
        Save the data in the simple requested format with detailed doctor info
        """
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"clinic_doctors_detailed_{timestamp}.txt"
        
        formatted_output = self.format_output_simple(doctors_data)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(formatted_output)
        
        return filename

    def save_json_format(self, doctors_data: list, filename: str = None):
        """
        Save the data in JSON format with your requested structure
        """
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"clinic_doctors_formatted_{timestamp}.json"
        
        formatted_data = self.format_output_json(doctors_data)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        
        return filename

    def cleanup(self):
        """Clean up Selenium resources"""
        if self.driver:
            self.driver.quit()
            print("🧹 Selenium driver closed")

def main():
    """Test the enhanced scraper with JSON format output"""
    print("🚀 HotDoc Enhanced Scraper with Selenium")
    print("=" * 45)
    
    scraper = SeleniumHotDocScraper()
    
    try:
        # Test URL - using the working Brisbane URL
        test_url = "https://www.hotdoc.com.au/medical-centres/brisbane-QLD-4000/centre-for-human-potential-brisbane/doctors"
        
        doctors = scraper.test_specific_url(test_url)
        
        if doctors:
            print(f"\n🎉 SUCCESS! Found {len(doctors)} doctors")
            
            # Save in JSON format
            json_file = scraper.save_json_format(doctors)
            print(f"💾 JSON format saved to: {json_file}")
            
            # Display the formatted JSON output
            print("\n" + "="*60)
            print("JSON FORMAT OUTPUT:")
            print("="*60)
            formatted_data = scraper.format_output_json(doctors)
            print(json.dumps(formatted_data, indent=2, ensure_ascii=False))
            
            # Also save raw data for reference
            with open('selenium_test_results_raw.json', 'w', encoding='utf-8') as f:
                json.dump(doctors, f, indent=2, ensure_ascii=False)
            print(f"💾 Raw data backup saved to: selenium_test_results_raw.json")
        else:
            print(f"\n⚠️  No doctors found.")
    
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    main()