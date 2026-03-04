# ntrx 🛰️ – RTK Distribucija Korekcionih Podataka

Dobrodošli u **ntrx**!  
NTRIP caster visokih performansi, zasnovan na asinhronom Python-u i Redis-u, koji koristi FastAPI i `asyncio`.

---

## 🚀 Ključne Funkcionalnosti

- **Redis-Native Arhitektura**: Koristi Redis Pub/Sub za komunikaciju između procesa (IPC).
  - **Live Slanje Pozicija**: Klijentske NMEA pozicije se šalju u Redis (`ntrip:positions`) u realnom vremenu.
  - **Kill Switch**: Administratorska kontrola aktivanog diskonektovanja korisnika putem Redis-a (`ntrip:control`).
- **Moderna Python Implementacija**:
  - Izgrađen na **Python 3.12+**, **FastAPI** i **AsyncIO** tehnologijama.
  - **Stroga Tipizacija**: Koristi **Pydantic** modele za svu razmenu podataka i upravljanje stanjem.
  - **Čist Kod**: Poštuje SOLID principe, nisku ciklomatsku složenost i objektno-orijentisani dizajn.
- **Skalabilnost**: Stateless dizajn omogućava horizontalno skaliranje API instanci.

---

## 🧩 Arhitektura

Posetite [ARCHITECTURE.Srpski.md](ARCHITECTURE.Srpski.md) za detaljne dijagrame i šemu sistema.

- **NTRIP Caster**: Upravlja konekcijama izvora (baza) i klijenata, parsira NMEA poruke i publikuje događaje u Redis.
- **FastAPI Server**: Obezbeđuje REST/WebSocket API za nadzor i kontrolu (Kill Switch).
- **Redis**: Centralna magistrala za poruke o pozicijama (`positions`), kontrolne komande (`control`) i deljeno stanje (`state`).

---

## ⚡ Brzi Start

### 1. Preduslovi

- Python 3.12+
- Redis Server (lokalni ili udaljeni)

### 2. Instalacija

```bash
git clone https://github.com/ndjuric/ntrx.git
cd ntrx
python -m venv venv
source venv/bin/activate
pip install -e .  # Instalacija u "editable" modu
```

### 3. Konfiguracija

Kreirajte `.env` fajl u korenom direktorijumu projekta:

```env
REDIS_HOST=127.0.0.1
REDIS_PASSWORD=changeme
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
LOG_MAX_SIZE_MB=10
LOG_MAX_BACKUP_COUNT=5
```

Izmenite `storage/ntripcaster.json` da biste definisali kredencijale za Izvore (Sources) i Klijente (Clients).

### 4. Pokretanje Sistema

Potrebno je pokrenuti Redis, Caster i API.

**Opcija A: Pojedinačni Procesi**

1. Pokrenite Redis: `docker-compose up -d`
2. Pokrenite API: `python -m ntrx api`
3. Pokrenite Caster: `python -m ntrx ntrip`

**Opcija B: CLI Pomoćni Alat**

```bash
python -m ntrx --help
```

> **Napomena**: Redis je **opcioni**. Ako Redis nije pokrenut, caster i API će se pokrenuti u **degradiranom modu** — osnovna NTRIP funkcionalnost radi, ali objavljivanje stanja u realnom vremenu, strimovanje pozicija i kontrolni kanal (kill switch) neće biti dostupni. Program automatski detektuje `docker-compose.yml` u korenom direktorijumu i predlaže `docker-compose up -d` ako Redis nije dostupan.

> **TODO – Operativni Modovi**: Dva moda su planirana:
> 1. **Standalone** *(trenutni)* – mountpoint-ovi i stanje se čuvaju u memoriji; Redis je opcionalan (samo za IPC).
> 2. **Thin Client** – mountpoint-ovi i kompletno stanje se čuvaju u Redis-u; caster postaje stateless, što omogućava horizontalno skaliranje iza load balancer-a.

---

## 📡 API Krajnje Tačke (Endpoints)

- `GET /state` – Vraća trenutno stanje sistema (povezani izvori/klijenti).
- `POST /api/kill/{username}` – Momentlano diskonektuje korisnika (Bazu ili Klijenta).
- `WS /ws` – Ažuriranje stanja u realnom vremenu putem WebSocket-a.
- `GET /` & `GET /debug/routes` - Pomoćni alati za debagovanje.

---

## 🧪 Testiranje i Verifikacija

Projekat sadrži robustan set integracionih testova za verifikaciju celog pajpalajna (Soket -> Caster -> Redis -> API).

```bash
# Verifikacija konekcije, slanja podataka i kill switch-a
python src/ntrx/tests/integration_test.py
```

---

## 🤝 Doprinos Projektu (Contributing)

- Kod mora koristiti **Pydantic** modele za sve strukture podataka.
- Sva komunikacija između procesa (IPC) mora ići kroz **Redis**.
- Ciklomatska složenost metoda mora biti ispod 10.
- Obavezno poštovanje **Objektno-Orijentisane** strukture (Class-Based).

---

## 📄 Licenca

MIT Licenca
