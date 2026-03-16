# Cardio Trainer

Aplikacja desktopowa do monitorowania i analizy treningów na rowerze stacjonarnym. Łączy się z czujnikami BLE (Bluetooth Low Energy) i wyświetla dane fitness w czasie rzeczywistym.

## 🎯 Główne funkcje:

- **Monitowanie tętna** – odczyt z czujników (np. Polar H10)
- **Pomiary mocy** – dane z power metrów (Stages, Quarq)
- **Kontrola trenażera** – sterowanie Elite Real Turbo Muin+ w trybie ERG lub symulacji
- **Odkrywanie urządzeń** – skanowanie BLE z poziomem sygnału (RSSI) i stanem baterii
- **Kalibracja** – Zero-offset dla power metrów
- **Statystyki sesji** – TSS, IF, NP, spalane kalorie (aktualizowane co sekundę)
- **Konfiguracja** – zapamiętywanie ostatnio używanych urządzeń

## 📁 Struktura kodu:

| Moduł | Przeznaczenie |
|-------|--------------|
| `connection/` | Skanowanie i zarządzanie połączeniami BLE |
| `logic/` | Obliczenia, konwersje i kalibracja |
| `ui/` | Interfejs PyQt5 (okna, widgety, stylowanie) |
| `trainer/` | Sterowanie Elite Muin+ (protokół FTMS) |
| `config/` | Zarządzanie konfiguracją i czujnikami |

## 🔧 Plik `main.py` (punkt wejścia):

1. **Parsowanie argumentów** – obsługuje opcjonalny parametr `--log-level` (DEBUG/INFO/WARNING/ERROR)
2. **Konfiguracja logerowania** – logi z czasem, poziomem i nazwą modułu
3. **Inicjalizacja PyQt5**:
   - Tworzenie aplikacji
   - Ustawianie metadanych (nazwa, wersja, organizacja)
4. **Załadowanie konfiguracji** – `ConfigManager` wczytuje czujniki z pliku JSON
5. **Wyświetlanie głównego okna** – `MainWindow` pobiera konfigurację
6. **Uruchomienie pętli zdarzeń** – `app.exec_()` blokuje do zamknięcia aplikacji

## 📦 Zależności:

- **bleak** ≥0.21.0 – biblioteka BLE
- **PyQt5** ≥5.15.0 – interfejs graficzny
- **pydantic** ≥2.0.0 – walidacja danych

Aplikacja jest dobrze zorganizowana z jasnym podziałem odpowiedzialności między modułami.

## 🔄 Współdzielenie plików przez VS Code i GitHub

### Inicjalna konfiguracja:

1. **Zainstaluj Git** – pobierz z https://git-scm.com/
2. **Skonfiguruj Git** (otwórz terminal i wykonaj):
   ```bash
   git config --global user.name "Twoje Imię"
   git config --global user.email "twoj.email@example.com"
   ```

### Klonowanie repozytorium:

1. W VS Code: `Ctrl+Shift+G` → Zaloguj się do GitHub
2. Kliknij **„Clone Repository"** i wklej adres repozytorium
3. Wybierz folder docelowy
4. VS Code automatycznie otworzy projekt

### Praca z kodem i wysyłanie zmian:

1. **Edytowanie plików** – zmienia są widoczne w zakładce Source Control (ikonka rozwidlenia)
2. **Podgląd zmian** – kliknij na plik w panelu Source Control, aby zobaczyć różnice
3. **Stage plików** (przygotowanie do commitu):
   - Kliknij `+` obok pojedynczego pliku lub
   - Kliknij `+` przy "Changes" aby przygotować wszystkie
4. **Commit** – wpisz wiadomość w polu tekstowym i kliknij ✓ (lub `Ctrl+Enter`)
5. **Push na GitHub** – kliknij przycisk `⋯` → Sync Changes (lub `Ctrl+Shift+P` → Git: Push)

### Pobieranie zmian z GitHub:

- Kliknij przycisk Sync Changes (`⇅`) aby automatycznie pobrać i wysłać zmiany
- Lub ręcznie: `Ctrl+Shift+P` → Git: Pull

### Tworzenie nowej gałęzi (branch):

1. Kliknij nazwę bieżącej gałęzi w dolnym pasku VS Code
2. Wybierz **„Create new branch"**
3. Wpisz nazwę (np. `feature/monitoring`)
4. Wybierz gałąź źródłową (zazwyczaj `main`)
5. Po zakończeniu pracy: stwórz Pull Request na GitHub

### Przydatne skróty klawiszowe VS Code:

| Akcja | Skrót |
|-------|-------|
| Source Control | `Ctrl+Shift+G` |
| Terminal | ``Ctrl+` `` |
| Git: Commit All | `Ctrl+Shift+K` |
| Git: Push | `Ctrl+Shift+P` → Git: Push |
| Git: Pull | `Ctrl+Shift+P` → Git: Pull |
| Command Palette | `Ctrl+Shift+P` |

### Dobre praktyki:

- ✅ **Commit regularnie** – małe, logiczne zmiany
- ✅ **Wiadomości commitów** – opisowe i w języku polskim lub angielskim
- ✅ **Pull request** – przed merge'em do `main`
- ✅ **Ignorowanie plików** – dodaj `__pycache__`, `.env`, `venv/` do `.gitignore`
- ❌ Nie wysyłaj haseł i tokenów – użyj zmiennych środowiskowych
