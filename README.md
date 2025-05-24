# Mail-in-a-Box DNS CLI Tool

This is a command-line tool for managing DNS records on a [Mail-in-a-Box](https://mailinabox.email) server using its admin API.

---

## 🛠 Setup Instructions

1. **Install dependencies** (Python 3.7+ recommended):

```bash
pip install requests python-dotenv tabulate
```

2. **Save the script** as `miab_dns_cli.py` and make it executable:

```bash
chmod +x miab_dns_cli.py
```

3. **Configure your environment:**

Run:

```bash
./miab_dns_cli.py --setup-env
```

You will be prompted to enter:
- `MIAB_HOST` – your box hostname (e.g. `box.example.com`)
- `MIAB_EMAIL` – your Mail-in-a-Box admin email
- `MIAB_PASSWORD` – your Mail-in-a-Box admin password

These values are securely saved in a `.env` file in the script's directory.

---

## 💡 Usage

Run `./miab_dns_cli.py -h` to see all available commands.

### 🔍 View Records

- List all DNS records:

```bash
./miab_dns_cli.py list-records
```

- List records for a specific domain:

```bash
./miab_dns_cli.py list-records example.com
```

- Get a specific record:

```bash
./miab_dns_cli.py get-record test.example.com A
```

---

### ➕ Add Records

- Add a new record (asks if it exists):

```bash
./miab_dns_cli.py add-record test.example.com A 1.2.3.4
```

- Force update if record exists:

```bash
./miab_dns_cli.py add-record test.example.com A 5.6.7.8 --update
```

- Forcefully overwrite:

```bash
./miab_dns_cli.py update-record test.example.com A 5.6.7.8
```

---

### ❌ Remove Record

```bash
./miab_dns_cli.py remove-record test.example.com A
```

---

### 🌐 DNS Zones

- List zones:

```bash
./miab_dns_cli.py list-zones
```

- View zonefile:

```bash
./miab_dns_cli.py get-zonefile example.com
```

---

### 🛰 Secondary Nameservers

- Get list:

```bash
./miab_dns_cli.py get-secondary-ns
```

- Add new:

```bash
./miab_dns_cli.py add-secondary-ns ns1.example.net,ns2.example.net
```

---

### 🔄 Apply DNS Changes

```bash
./miab_dns_cli.py update-dns
```

Use `--force` to apply changes even without detected modifications.

---

## 📁 Example .env file (auto-created)

```env
MIAB_HOST=box.example.com
MIAB_EMAIL=admin@example.com
MIAB_PASSWORD=yourpassword
```

---

## 🔐 Security Note

The `.env` file contains credentials. Do not commit this file to version control.

---

## 📄 License

MIT. Use at your own risk. Not affiliated with the official Mail-in-a-Box project.