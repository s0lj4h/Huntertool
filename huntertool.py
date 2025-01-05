import os
import re
import requests
import json
import csv
import logging
from datetime import datetime
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd


# --------------------
# Utility Functions
# --------------------

def is_valid_domain(domain: str) -> bool:
    """
    Basic domain format validation using a simple regex.
    Note: This won't cover all edge cases but helps weed out invalid input.
    """
    pattern = r"^(?!-)([A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,6}$"
    return bool(re.match(pattern, domain))


def is_valid_email_format(email: str) -> bool:
    """
    Basic email format validation using a regex.
    """
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


@dataclass
class HunterEmailTool:
    """
    A client for interacting with the Hunter.io API to search for
    domain email patterns, find specific emails, and verify them.
    
    Endpoints used:
      - /domain-search   -> domain_search()
      - /email-finder    -> email_finder()
      - /email-verifier  -> email_verifier()
    """
    api_key: str
    base_url: str = "https://api.hunter.io/v2"

    def __post_init__(self) -> None:
        """
        Perform additional initialization tasks after the dataclass is created.
        """
        self._setup_logging()

    def _setup_logging(self) -> None:
        """
        Configure logging for this client.
        """
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    # ------------------------
    # Core API Methods
    # ------------------------

    def domain_search(self, domain: str) -> Dict:
        """
        Performs a domain search via Hunter.io.
        Official usage:
          GET https://api.hunter.io/v2/domain-search?domain=<DOMAIN>&api_key=<API_KEY>
        """
        if not is_valid_domain(domain):
            raise ValueError(f"Invalid domain format: {domain}")

        try:
            response = requests.get(
                f"{self.base_url}/domain-search",
                params={
                    "domain": domain,
                    "api_key": self.api_key
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            # The API may provide an 'emails_count', but it could be zero or missing.
            # We'll rely on the length of the 'emails' list for an accurate count.
            emails_list = data["data"].get("emails", [])

            return {
                "domain": domain,
                "pattern": data["data"].get("pattern"),
                "organization": data["data"].get("organization"),
                "emails": [
                    {
                        "value": email["value"],
                        "type": email["type"],
                        "confidence": email["confidence"],
                        "first_name": email.get("first_name"),
                        "last_name": email.get("last_name"),
                        "position": email.get("position"),
                        "department": email.get("department"),
                        "seniority": email.get("seniority"),
                        # role information if found
                        "role": email.get("role"),
                    }
                    for email in emails_list
                ],
                "email_count": len(emails_list),
            }
        except requests.exceptions.RequestException as exc:
            self.logger.error("Error searching domain %s: %s", domain, str(exc))
            raise

    def email_finder(
        self,
        domain: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> Dict:
        """
        Finds an email address using domain + name details.
        Official usage:
          GET https://api.hunter.io/v2/email-finder?domain=<DOMAIN>&first_name=<FIRST>&last_name=<LAST>&api_key=<API_KEY>
        """
        if not is_valid_domain(domain):
            raise ValueError(f"Invalid domain format: {domain}")

        # Build query params
        params = {
            "domain": domain,
            "api_key": self.api_key
        }

        # If a full_name is provided, attempt to parse it into first/last
        if full_name:
            names = full_name.strip().split()
            if len(names) >= 2:
                params["first_name"] = names[0]
                params["last_name"] = names[-1]
        else:
            if first_name:
                params["first_name"] = first_name.strip()
            if last_name:
                params["last_name"] = last_name.strip()

        try:
            response = requests.get(
                f"{self.base_url}/email-finder",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "email": data["data"].get("email"),
                "confidence": data["data"].get("confidence"),
                "sources": data["data"].get("sources", []),
                "first_name": data["data"].get("first_name"),
                "last_name": data["data"].get("last_name"),
                "position": data["data"].get("position"),
                "twitter": data["data"].get("twitter"),
                "linkedin_url": data["data"].get("linkedin_url"),
                # role information if found
                "role": data["data"].get("role"),
            }
        except requests.exceptions.RequestException as exc:
            self.logger.error("Error finding email for domain '%s': %s", domain, str(exc))
            raise

    def email_verifier(self, email: str) -> Dict:
        """
        Verifies an email address.
        Official usage:
          GET https://api.hunter.io/v2/email-verifier?email=<EMAIL>&api_key=<API_KEY>
        """
        if not is_valid_email_format(email):
            raise ValueError(f"Invalid email format: {email}")

        try:
            response = requests.get(
                f"{self.base_url}/email-verifier",
                params={
                    "email": email,
                    "api_key": self.api_key
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "email": email,
                "result": data["data"].get("result"),
                "score": data["data"].get("score"),
                "regexp": data["data"].get("regexp"),
                "gibberish": data["data"].get("gibberish"),
                "disposable": data["data"].get("disposable"),
                "webmail": data["data"].get("webmail"),
                "mx_records": data["data"].get("mx_records"),
                "smtp_server": data["data"].get("smtp_server"),
                "smtp_check": data["data"].get("smtp_check"),
                "accept_all": data["data"].get("accept_all"),
                "block": data["data"].get("block"),
                "sources": data["data"].get("sources", []),
            }
        except requests.exceptions.RequestException as exc:
            self.logger.error("Error verifying email %s: %s", email, str(exc))
            raise

    # --------------------------------------
    # Batch Methods (With Optional Concurrency)
    # --------------------------------------

    def batch_verify_emails(
        self,
        emails: List[str],
        output_file: Optional[str] = None,
        use_concurrency: bool = False,
        max_workers: int = 5,
    ) -> List[Dict]:
        """
        Verifies multiple email addresses, optionally in parallel.
        """
        results: List[Dict] = []
        # Filter out invalid emails first
        emails_to_process = [e for e in emails if is_valid_email_format(e)]
        invalid_emails = [e for e in emails if not is_valid_email_format(e)]

        if invalid_emails:
            self.logger.warning("Skipping invalid emails: %s", invalid_emails)

        if use_concurrency and emails_to_process:
            self.logger.info("Starting concurrent email verification with %d workers...", max_workers)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_email = {
                    executor.submit(self.email_verifier, email): email
                    for email in emails_to_process
                }
                for future in as_completed(future_to_email):
                    email = future_to_email[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as exc:
                        results.append({"email": email, "error": str(exc)})
        else:
            # Sequential approach
            total = len(emails_to_process)
            for i, email in enumerate(emails_to_process, start=1):
                self.logger.info("Verifying email %d/%d: %s", i, total, email)
                try:
                    result = self.email_verifier(email)
                    results.append(result)
                except Exception as exc:
                    results.append({"email": email, "error": str(exc)})

        if output_file:
            self.export_results(results, output_file)

        return results

    def batch_domain_search(
        self,
        domains: List[str],
        output_file: Optional[str] = None,
        use_concurrency: bool = False,
        max_workers: int = 5,
    ) -> List[Dict]:
        """
        Searches multiple domains, optionally in parallel.
        """
        results: List[Dict] = []
        # Filter out invalid domains first
        domains_to_process = [d for d in domains if is_valid_domain(d)]
        invalid_domains = [d for d in domains if not is_valid_domain(d)]

        if invalid_domains:
            self.logger.warning("Skipping invalid domains: %s", invalid_domains)

        if use_concurrency and domains_to_process:
            self.logger.info("Starting concurrent domain searches with %d workers...", max_workers)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_domain = {
                    executor.submit(self.domain_search, d): d
                    for d in domains_to_process
                }
                for future in as_completed(future_to_domain):
                    domain = future_to_domain[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as exc:
                        results.append({"domain": domain, "error": str(exc)})
        else:
            # Sequential approach
            total = len(domains_to_process)
            for i, domain in enumerate(domains_to_process, start=1):
                self.logger.info("Searching domain %d/%d: %s", i, total, domain)
                try:
                    result = self.domain_search(domain)
                    results.append(result)
                except Exception as exc:
                    results.append({"domain": domain, "error": str(exc)})

        if output_file:
            self.export_results(results, output_file)

        return results

    # -----------------------
    # Exporting Results
    # -----------------------

    def export_results(self, results: List[Dict], output_file: str) -> None:
        """
        Exports results to a file (CSV or JSON), timestamped to avoid overwrites.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if "." in output_file:
            base_name, ext = output_file.rsplit(".", 1)
        else:
            base_name, ext = output_file, "csv"

        filename = f"{base_name}_{timestamp}.{ext}"

        try:
            if ext.lower() == "json":
                with open(filename, "w", encoding="utf-8") as file:
                    json.dump(results, file, indent=2)
            else:
                # Convert to pandas DataFrame for easy CSV export
                df = pd.json_normalize(results)
                df.to_csv(filename, index=False, encoding="utf-8")

            self.logger.info("Results exported to %s", filename)
        except Exception as exc:
            self.logger.error("Error exporting results to %s: %s", filename, str(exc))
            raise


def main() -> None:
    """
    Main function showcasing an interactive menu for the HunterEmailTool.
    Corrected so:
      - We rely on the length of the 'emails' list for counting
      - We save the Name and Position in the txt file
    """
    # Retrieve API key from environment variable or fallback
    api_key = os.getenv("HUNTER_API_KEY", "")
    if not api_key or api_key == "your-hunter-api-key":
        print("No valid Hunter API key found. Please set HUNTER_API_KEY environment variable.")
        return

    hunter = HunterEmailTool(api_key=api_key)

    while True:
        print("\nHunter.io Email Tool Menu:")
        print("1. Domain Search")
        print("2. Email Finder")
        print("3. Email Verification")
        print("4. Batch Email Verification")
        print("5. Batch Domain Search")
        print("6. Exit")

        choice = input("\nSelect an option (1-6): ").strip()
        if choice == "1":
            domain = input("Enter domain: ").strip()
            try:
                result = hunter.domain_search(domain)
                emails_list = result["emails"]

                # Overwrite the "email_count" with the actual length
                result["email_count"] = len(emails_list)

                print("\nDomain Information:")
                print(f"Pattern: {result.get('pattern')}")
                print(f"Organization: {result.get('organization')}")
                print(f"Total emails found: {result['email_count']}")
                print("\nEmail Addresses:")
                for email_info in emails_list:
                    print(f"\nEmail: {email_info.get('value')}")
                    print(f"Confidence: {email_info.get('confidence')}")
                    print(f"Type: {email_info.get('type')}")
                    if email_info.get("first_name") or email_info.get("last_name"):
                        print(f"Name: {email_info.get('first_name', '')} {email_info.get('last_name', '')}")
                    if email_info.get("position"):
                        print(f"Position: {email_info['position']}")

                # If multiple emails found, prompt to save
                if len(emails_list) > 1:
                    save_choice = input(
                        "\nMultiple emails found. Save results to a .txt file? (y/n): "
                    ).lower().strip()
                    if save_choice == "y":
                        txt_filename = f"domain_search_{domain}.txt"
                        try:
                            with open(txt_filename, "w", encoding="utf-8") as f:
                                f.write(f"Domain: {domain}\n")
                                f.write(f"Pattern: {result.get('pattern')}\n")
                                f.write(f"Organization: {result.get('organization')}\n")
                                f.write(f"Total Emails: {result['email_count']}\n\n")
                                f.write("Emails:\n")
                                for email_info in emails_list:
                                    email_val = email_info.get('value')
                                    confidence = email_info.get('confidence')
                                    f_name = email_info.get('first_name', '')
                                    l_name = email_info.get('last_name', '')
                                    position = email_info.get('position', '')

                                    f.write(f" - {email_val} (Confidence: {confidence})\n")
                                    if f_name or l_name:
                                        f.write(f"   Name: {f_name} {l_name}\n")
                                    if position:
                                        f.write(f"   Position: {position}\n")
                            print(f"Results saved to {txt_filename}")
                        except Exception as e:
                            print(f"Error saving to txt file: {e}")

            except Exception as exc:
                print(f"Error: {str(exc)}")

        elif choice == "2":
            domain = input("Enter domain: ").strip()
            search_type = input("Search by (1) First/Last Name or (2) Full Name? ").strip()
            try:
                if search_type == "1":
                    first_name = input("Enter first name: ").strip()
                    last_name = input("Enter last name: ").strip()
                    result = hunter.email_finder(domain, first_name=first_name, last_name=last_name)
                else:
                    full_name = input("Enter full name: ").strip()
                    result = hunter.email_finder(domain, full_name=full_name)

                print("\nEmail Finder Results:")
                print(f"Email: {result.get('email')}")
                print(f"Confidence: {result.get('confidence')}")
                print(f"Name: {result.get('first_name')} {result.get('last_name')}")
                if result.get("position"):
                    print(f"Position: {result['position']}")

                sources = result.get("sources", [])
                if len(sources) > 1:
                    save_choice = input(
                        "\nMultiple sources found. Save results to a .txt file? (y/n): "
                    ).lower().strip()
                    if save_choice == "y":
                        txt_filename = f"email_finder_{domain}.txt"
                        try:
                            with open(txt_filename, "w", encoding="utf-8") as f:
                                f.write(f"Domain: {domain}\n")
                                f.write(f"Email: {result.get('email')}\n")
                                f.write(f"Confidence: {result.get('confidence')}\n")
                                f.write(f"Name: {result.get('first_name')} {result.get('last_name')}\n")
                                if result.get("position"):
                                    f.write(f"Position: {result['position']}\n")
                                f.write("\nSources:\n")
                                for src in sources:
                                    f.write(f" - {src}\n")
                            print(f"Results saved to {txt_filename}")
                        except Exception as e:
                            print(f"Error saving to txt file: {e}")

            except Exception as exc:
                print(f"Error: {str(exc)}")

        elif choice == "3":
            email_input = input("Enter email to verify: ").strip()
            try:
                result = hunter.email_verifier(email_input)
                print("\nVerification Results:")
                print(f"Result: {result.get('result')}")
                print(f"Score: {result.get('score')}")
                print(f"Disposable: {result.get('disposable')}")
                print(f"Webmail: {result.get('webmail')}")
                print(f"MX Records: {result.get('mx_records')}")
                print(f"SMTP Check: {result.get('smtp_check')}")
                if result.get("sources"):
                    print(f"Found in {len(result['sources'])} sources")
            except Exception as exc:
                print(f"Error: {str(exc)}")

        elif choice == "4":
            input_file = input("Enter path to input file (one email per line): ").strip()
            output_format = input("Enter output format (csv/json): ").lower().strip()
            output_file = input("Enter output file path (without extension): ").strip()
            concurrency = input("Use concurrency? (y/n): ").lower().strip() == "y"

            try:
                with open(input_file, "r", encoding="utf-8") as file:
                    emails = [line.strip() for line in file if line.strip()]

                print(f"\nProcessing {len(emails)} emails...")
                hunter.batch_verify_emails(
                    emails,
                    output_file=f"{output_file}.{output_format}",
                    use_concurrency=concurrency,
                    max_workers=5,
                )
                print("Batch verification completed!")
            except Exception as exc:
                print(f"Error: {str(exc)}")

        elif choice == "5":
            input_file = input("Enter path to input file (one domain per line): ").strip()
            output_format = input("Enter output format (csv/json): ").lower().strip()
            output_file = input("Enter output file path (without extension): ").strip()
            concurrency = input("Use concurrency? (y/n): ").lower().strip() == "y"

            try:
                with open(input_file, "r", encoding="utf-8") as file:
                    domains = [line.strip() for line in file if line.strip()]

                print(f"\nProcessing {len(domains)} domains...")
                hunter.batch_domain_search(
                    domains,
                    output_file=f"{output_file}.{output_format}",
                    use_concurrency=concurrency,
                    max_workers=5,
                )
                print("Batch domain search completed!")
            except Exception as exc:
                print(f"Error: {str(exc)}")

        elif choice == "6":
            print("Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()