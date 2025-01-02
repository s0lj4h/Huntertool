# HunterTool

## Table of Contents
1. [Overview](#overview)  
2. [Features](#features)  
3. [Prerequisites](#prerequisites)  
4. [Installation & Setup](#installation--setup)  
5. [Usage](#usage)  
   - [Command-Line Menu](#command-line-menu)  
   - [Batch Processing](#batch-processing)  
 

---

## Overview

This script provides a **command-line interface (CLI)** for interacting with [Hunter.io](https://hunter.io/) API.  
It can:

- **Search** a domain to discover email patterns and addresses.  
- **Find** (guess) an email if you know someone’s name and their company’s domain.  
- **Verify** if an email address is valid or deliverable.  
- Process lists of emails or domains in **batch mode**, optionally with concurrency to speed up large jobs.

It relies on a **Hunter.io** API key (which you must provide) and performs HTTP calls to Hunter.io endpoints. You can either do single lookups (interactive prompts) or run bulk operations from a file.

Sign up for a free account (100 queries per month) at Hunter.io. (Note: you cannot register with a free email account) copy your API key from https://hunter.io/api-keys

---

## Features

**Domain Search**  
- Given a domain (e.g. `tesla.com`) discovers potential email addresses, or organizational info.

**Email Finder**  
- Provide a domain and name (full or first/last), and attempt to find a matching email address.

**Email Verification**  
- Check if an email is deliverable, disposable, or belongs to a catch-all domain.

**Batch Processing**  
- Read a list of emails or domains from a file, optionally use concurrency (multi-threading), and export results to CSV or JSON.

**Logging & Saving to .txt**  
- Prints output (info/errors) to the console.
- Results can be saved to a `.txt` file.

---

## Prerequisites

- **Python 3.7 or higher**  
- A **Hunter.io** [API key]([https://hunter.io/](https://hunter.io/api-keys))  
- Libraries:
  ```bash
  pip install requests pandas

  ```

## Installation & Setup

1. Clone or Download this repository.    
2. Install dependencies:    
```bash
pip install requests pandas

```
Register to Hunter.io using a buisness email.    
Copy your API key from https://hunter.io/api-keys  
Set your API key as an environment variable:  
```bash
# On macOS/Linux
export HUNTER_API_KEY="YOUR_API_KEY"

# On Windows
set HUNTER_API_KEY=YOUR_API_KEY

```
Run the script:
```bash
python huntertool.py
```

---


