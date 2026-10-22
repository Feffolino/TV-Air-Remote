# TV Air Remote — Specifica di design

Data: 2026-10-22
Stato: approvata in brainstorming, in attesa di revisione finale

## 1. Obiettivo

Controllare una Smart TV Samsung (Tizen), usata principalmente come televisore
tradizionale, tramite gesture delle mani riprese da una webcam e riconosciute
in tempo reale. Priorità: cambio canale e volume rapidi e affidabili; la
navigazione nei menu è secondaria.

### Vincoli

- Riconoscimento su PC/portatile con webcam (Python).
- TV Samsung Tizen controllata via WebSocket (porta 8002, TLS) con `samsungtvws`.
- Controllo sempre attivo: nessuna gesture di sblocco, i falsi comandi si
  prevengono con filtri di stabilità, gesture tenute e swipe "armati".
- Nessun training di modelli: si usano le gesture predefinite di MediaPipe
  Gesture Recognizer più swipe calcolati dal movimento del polso.

### Fuori ambito (per ora)

- Inserimento diretto del numero di canale contando le dita.
- Controllo di altri dispositivi smart o hub (Home Assistant, MQTT).
- Esecuzione su Raspberry Pi, browser o smartphone (il codice resta portabile).

## 2. Architettura

Un solo processo Python. Il ciclo camera/riconoscimento gira nel thread
principale; l'invio dei comandi alla TV avviene in un thread separato tramite
coda, così la latenza di rete non blocca il video.

```
webcam ─► camera.py ─► recognizer.py ─► interpreter.py ─► tv.py ─► TV Samsung
          (OpenCV,      (MediaPipe        (stabilità, hold,  (thread + coda,
           specchiato)   GestureRecognizer, ripetizione,      samsungtvws,
                         modalità VIDEO)    swipe, modalità)   Wake-on-LAN)
                                    └──► overlay.py (landmark, modalità,
                                                     gesture, ultimo tasto,
                                                     stato TV)
```

## 3. Mappatura delle gesture

Il sistema ha due modalità. La modalità attiva è mostrata nell'overlay.

Nomi delle gesture MediaPipe: `Thumb_Up`, `Thumb_Down`, `Victory`,
`Pointing_Up`, `ILoveYou`, `Closed_Fist`, `Open_Palm`.

### 3.1 Modalità TV (predefinita)

| Gesture | Tasto inviato | Regola |
|---|---|---|
| Swipe ↑ | `KEY_CHUP` | un canale per swipe, cooldown 500 ms |
| Swipe ↓ | `KEY_CHDOWN` | un canale per swipe, cooldown 500 ms |
| `Thumb_Up` | `KEY_VOLUP` | ripetuto ogni 300 ms finché tenuto; dopo 1,5 s ogni 150 ms |
| `Thumb_Down` | `KEY_VOLDOWN` | come sopra |
| `Victory` | alterna `KEY_PAUSE` / `KEY_PLAY` | primo invio `KEY_PAUSE` |
| `Pointing_Up` tenuto 1 s | `KEY_HOME` | passa a modalità Navigazione |
| `ILoveYou` tenuto 1,5 s | `KEY_POWER` | Wake-on-LAN se la TV è spenta (vedi §5) |
| `Closed_Fist` | nessuno | — |
| Swipe ← / → | nessuno | lasciati liberi per ridurre i falsi comandi |
| `Open_Palm` fermo | nessuno | posa neutra da cui partono gli swipe |

Play/pausa: il protocollo Samsung non ha un tasto toggle affidabile su tutti i
modelli, quindi l'interprete memorizza l'ultimo stato e alterna `KEY_PAUSE` e
`KEY_PLAY`. Se lo stato si desincronizza (uso del telecomando fisico), una
seconda gesture lo riallinea. Sui canali in diretta la pausa dipende dal
timeshift della TV, che su molti modelli richiede una memoria USB.

### 3.2 Modalità Navigazione

| Gesture | Tasto inviato |
|---|---|
| Swipe ↑ / ↓ / ← / → | `KEY_UP` / `KEY_DOWN` / `KEY_LEFT` / `KEY_RIGHT` |
| `Closed_Fist` | `KEY_ENTER` |
| `Victory` | `KEY_RETURN` |
| `Thumb_Up` / `Thumb_Down` | `KEY_VOLUP` / `KEY_VOLDOWN` (stesse regole della modalità TV) |
| `Pointing_Up` tenuto 1 s | `KEY_EXIT`, ritorno a modalità TV |
| `ILoveYou` tenuto 1,5 s | `KEY_POWER` |

Ritorno automatico alla modalità TV dopo 8 s senza comandi inviati.

### 3.3 Filtri contro i falsi comandi

- **Stabilità:** una gesture statica è valida solo dopo 5 frame consecutivi
  con la stessa etichetta e confidenza ≥ 0,7.
- **Cooldown:** 800 ms dopo ogni comando singolo (non si applica alle
  ripetizioni del volume; per tutti gli swipe, in entrambe le modalità, vale
  500 ms).
- **Un invio per gesture:** le gesture non ripetute (`Victory`,
  `Closed_Fist`, `Pointing_Up`, `ILoveYou`) inviano un solo comando finché
  restano tenute; per ripeterle bisogna cambiare gesture o togliere la mano.
- **Swipe armato:** uno swipe è valido solo se la mano era in `Open_Palm`
  quasi ferma (spostamento del polso < 3% del frame) per almeno 0,3 s, e poi
  il polso si sposta di oltre il 25% della dimensione del frame entro 0,4 s.
  La direzione è l'asse con lo spostamento maggiore.
- **Una mano:** MediaPipe traccia una sola mano (`num_hands=1`).
- **Perdita della mano:** dopo 300 ms senza mano l'interprete azzera hold,
  ripetizioni e armamento dello swipe.

Tutte le soglie sono configurabili in `config.yaml`.

## 4. Componenti

Pacchetto `tv_air_remote/`.

### 4.1 `config.py` + `config.yaml`

Carica e valida la configurazione in dataclass:

- `tv`: `host`, `port` (default 8002), `mac` (opzionale, per Wake-on-LAN),
  `token_file` (default `.tv_token`), `name` (default `TV Air Remote`).
- `camera`: `index` (default 0), `width` 640, `height` 480, `fps` 30.
- `thresholds`: tutte le soglie del §3.3, i tempi di hold, di ripetizione e
  di ritorno automatico.
- `mapping`: per ciascuna modalità, gesture → tasto.

I tasti sono validati contro un elenco di tasti Samsung noti; un tasto non
valido o un campo obbligatorio mancante interrompono l'avvio con un messaggio
che indica campo e valore.

### 4.2 `camera.py`

Wrapper di `cv2.VideoCapture`. Imposta risoluzione e FPS, specchia il frame
orizzontalmente (così "sinistra" dell'utente è sinistra a schermo) e
restituisce `(frame, t_ms)` con timestamp monotono.

### 4.3 `recognizer.py`

Wrapper di MediaPipe `GestureRecognizer` in modalità `VIDEO`, `num_hands=1`
(una sola mano tracciata in modo continuo: con due mani il polso potrebbe
saltare da una mano all'altra e generare swipe falsi).
Per ogni frame restituisce `HandObservation(gesture, score, wrist_xy,
landmarks, t_ms)` per la mano migliore, oppure `None`. `wrist_xy` è
normalizzato in [0, 1]. Se il modello `gesture_recognizer.task` manca in
`models/`, viene scaricato al primo avvio.

### 4.4 `swipe.py`

`SwipeDetector`: logica pura. Riceve le osservazioni e restituisce
`Direction` (`UP`, `DOWN`, `LEFT`, `RIGHT`) oppure `None`, applicando le
regole di armamento del §3.3.

### 4.5 `interpreter.py`

`GestureInterpreter`: macchina a stati pura, senza I/O, con orologio
iniettato (i timestamp arrivano dalle osservazioni). Metodo principale:
`update(observation | None, t_ms) -> list[str]` (lista di tasti da inviare).
Gestisce stabilità, gesture tenute, ripetizione con accelerazione, cooldown,
modalità e ritorno automatico, alternanza play/pausa. Espone la modalità
corrente e l'ultima gesture per l'overlay.

### 4.6 `tv.py`

`TvController`: avvolge `samsungtvws.SamsungTVWS(host, port=8002,
token_file=..., name=...)` in un thread dedicato con coda di massimo 5
elementi.

- `send(key)` non blocca; se la coda è piena scarta il comando più vecchio.
- `status`: `CONNECTED`, `DISCONNECTED`, `AWAITING_AUTH`, `AUTH_DENIED`.
- Supporta un'implementazione finta (`FakeTv`) per `--dry-run` e per i test.

### 4.7 `overlay.py`

Disegna sul frame landmark della mano, modalità corrente, gesture
riconosciuta con confidenza, ultimo tasto inviato e stato della TV.

### 4.8 `__main__.py`

Avvio con `python -m tv_air_remote`. Opzioni: `--config PATH`,
`--camera N`, `--dry-run`. Ciclo: camera → recognizer → interpreter →
`tv.send` → overlay. Uscita con `q` o `ESC`, chiusura ordinata di camera,
recognizer e thread TV.

## 5. Gestione degli errori

| Situazione | Comportamento |
|---|---|
| TV non raggiungibile all'avvio | L'app parte comunque; overlay "TV non connessa"; riconnessione in background con backoff 1, 2, 4… fino a 30 s. |
| Comandi con TV disconnessa | Scartati, non accodati: comandi arrivati in ritardo (es. dieci "volume su") sono peggio di comandi persi. Eccezione: `KEY_POWER` con `mac` configurato (riga sotto). |
| Primo collegamento | La TV mostra la richiesta "Consenti"; stato `AWAITING_AUTH`; il token viene salvato in `token_file`. |
| Autorizzazione negata | Stato `AUTH_DENIED`; l'overlay indica di riabilitare il dispositivo in Impostazioni > Generale > Gestione dispositivi esterni. |
| Connessione persa durante l'uso | L'errore di invio porta a `DISCONNECTED` e riavvia la riconnessione. |
| `KEY_POWER` con TV spenta | Se `mac` è configurato, invio di un pacchetto Wake-on-LAN (da abilitare sulla TV: Rete > Impostazioni esperto > Accensione con mobile). Senza `mac`, il comando viene scartato con un avviso nel log. |
| Mano persa > 300 ms | Azzeramento di hold e ripetizioni: il volume smette subito di cambiare. |
| Webcam assente o non apribile | Uscita con messaggio che indica l'indice della camera provato. |
| Modello assente e PC offline | Uscita con messaggio che riporta l'URL per il download manuale e il percorso di destinazione. |

## 6. Test

Framework: `pytest`.

- **`swipe.py`**: swipe valido in ciascuna direzione; swipe senza
  `Open_Palm` fermo prima → ignorato; spostamento sotto soglia → ignorato;
  movimento troppo lento (> 0,4 s) → ignorato.
- **`interpreter.py`** (sequenze sintetiche, orologio finto):
  - gesture stabile meno di 5 frame → nessun tasto;
  - confidenza < 0,7 → nessun tasto;
  - cooldown rispettato;
  - `ILoveYou` rilasciato prima di 1,5 s → nessun tasto;
  - volume: ripetizione a 300 ms, accelerazione a 150 ms dopo 1,5 s;
  - perdita della mano → la ripetizione si interrompe;
  - `Pointing_Up` tenuto 1 s → `KEY_HOME` e modalità Navigazione;
  - ritorno automatico a modalità TV dopo 8 s;
  - `Victory` alterna `KEY_PAUSE` e `KEY_PLAY` in modalità TV;
  - stessa gesture → tasti diversi in modalità diverse.
- **`tv.py`** con `SamsungTVWS` finto: riconnessione con backoff; comandi
  scartati da disconnessa; coda piena scarta il più vecchio; Wake-on-LAN su
  `KEY_POWER` a TV irraggiungibile con `mac` configurato.
- **`config.py`**: tasto non valido e campo mancante producono errori chiari.
- **Camera e riconoscimento**: nessun test automatico (richiedono hardware).
  Checklist manuale in `--dry-run` che esercita ogni gesture in entrambe le
  modalità.

## 7. Dipendenze

Python 3.11 o 3.12. Runtime: `mediapipe`, `opencv-contrib-python` (già richiesto
da mediapipe; non installare anche `opencv-python`), `samsungtvws`, `wakeonlan`,
`pyyaml`. Sviluppo: `pytest`.
