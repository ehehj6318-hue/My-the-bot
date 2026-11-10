import fitz  # PyMuPDF
import sys
import os
import string
import itertools
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

def log_progress(msg):
    print(f"PROGRESS|{msg}", flush=True)

# 🟢 Prefix Generator
def get_prefixes(name):
    # Remove everything except letters and take first 4 (Uppercase)
    clean = "".join(filter(str.isalpha, name)).upper()
    if len(clean) >= 4:
        return [clean[:4]]
    else:
        # If name is shorter than 4 characters (e.g. DEV), use it directly without padding
        return [clean]

def check_range(pdf_path, prefixes, year_range):
    """Worker function to check a list of prefixes against a year range."""
    # Each worker opens its own copy of the PDF
    try:
        doc = fitz.open(pdf_path)
        for prefix in prefixes:
            for year in year_range:
                t_pass = f"{prefix}{year}"
                if doc.authenticate(t_pass):
                    doc.close()
                    return t_pass
        doc.close()
    except:
        pass
    return None

def main():
    if len(sys.argv) < 6:
        print("ERROR|Missing arguments")
        sys.exit(1)

    pdf_path = sys.argv[1]
    name_hint = sys.argv[2]
    output_dir = sys.argv[3]
    req_id = sys.argv[4]
    is_premium = sys.argv[5].lower() == 'true'

    unlocked_pdf = os.path.join(output_dir, f"Unlocked_{req_id}.pdf")
    front_img = os.path.join(output_dir, f"Front_{req_id}.jpg")
    back_img = os.path.join(output_dir, f"Back_{req_id}.jpg")

    try:
        doc = fitz.open(pdf_path)
        if not doc:
            print("ERROR|Failed to open PDF")
            sys.exit(1)

        final_password = ""
        if doc.is_encrypted:
            auth_success = False
            
            # --- LEVEL 1: Smart Guess ---
            prefixes_smart = get_prefixes(name_hint)
            log_progress(f"Starting Smart Guess scan...")
            for p in prefixes_smart:
                for y in range(1940, 2027):
                    t_pass = f"{p}{y}"
                    if doc.authenticate(t_pass):
                        final_password = t_pass
                        auth_success = True
                        break
                if auth_success: break
            
            if not auth_success:
                print(f"UNCRACKED|{pdf_path}")
                sys.exit(0)

            # Re-verify and save
            doc.authenticate(final_password)
        
        doc.save(unlocked_pdf)
        
        # Extract Aadhaar Number — try multiple known formats
        aadhaar_number = "Not Found"
        page = doc[0]
        text = page.get_text("text")
        for line in text.split('\n'):
            line = line.strip()
            # Format: "XXXX XXXX XXXX" (14 chars with spaces)
            if len(line) == 14 and " " in line:
                parts = line.split(" ")
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    aadhaar_number = line
                    break
            # Format: "XXXXXXXXXXXX" (12 digit, no spaces)
            if len(line) == 12 and line.isdigit():
                aadhaar_number = f"{line[:4]} {line[4:8]} {line[8:]}"
                break
        
        # Render Images — detect if front/back are side-by-side (single page) or separate pages
        mat = fitz.Matrix(2, 2)
        w, h = page.rect.width, page.rect.height

        num_pages = len(doc)
        if num_pages >= 2:
            # Multi-page: page 0 = front, page 1 = back
            front_page = doc[0]
            back_page = doc[1]
            front_page.get_pixmap(matrix=mat).save(front_img)
            back_page.get_pixmap(matrix=mat).save(back_img)
        else:
            # Single-page side-by-side layout
            front_rect = fitz.Rect(w * 0.02, h * 0.60, w * 0.50, h * 0.98)
            back_rect  = fitz.Rect(w * 0.50, h * 0.60, w * 0.98, h * 0.98)
            pix_f = page.get_pixmap(matrix=mat, clip=front_rect)
            pix_b = page.get_pixmap(matrix=mat, clip=back_rect)
            if pix_f.width > 10:
                pix_f.save(front_img)
            else:
                page.get_pixmap(matrix=mat).save(front_img)
                import shutil; shutil.copy(front_img, back_img)
            pix_b.save(back_img)
        
        doc.close()
        print(f"SUCCESS|{aadhaar_number}|{unlocked_pdf}|{front_img}|{back_img}|{final_password}")

    except Exception as e:
        print(f"ERROR|{str(e)}")
        sys.exit(2)

if __name__ == "__main__":
    main()
