import os
import glob

def strip_null_bytes(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py") or file.endswith(".txt"):
                path = os.path.join(root, file)
                try:
                    with open(path, "rb") as f:
                        content = f.read()
                    
                    if b"\x00" in content:
                        print(f"Found null bytes in: {path}, converting...")
                        # If it's UTF-16 LE
                        content = content.decode("utf-16").encode("utf-8")
                        with open(path, "wb") as f:
                            f.write(content)
                        continue
                        
                    # Also normalize line endings and encoding
                    text = content.decode("utf-8-sig")
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(text)
                except Exception as e:
                    print(f"Error processing {path}: {e}")

strip_null_bytes(r"c:\Users\omsah\OneDrive\Desktop\Vs code\python prgms2\invoice-agent")
