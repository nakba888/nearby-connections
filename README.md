# 📡 Raspberry Pi Nearby Connections Detector (스마트폰 Advertiser ↔ 라즈베리파이 Discoverer)

스마트폰이 **Advertiser(신호 송출)** 역할을 하고, 라즈베리파이가 **Discoverer(신호 감지)** 역할을 하여 스마트폰의 접근과 근접도(RSSI)를 실시간 감지하는 프로젝트입니다.

---

## 📂 프로젝트 구조

```text
.
├── python/                      # [추천] 라즈베리파이용 가벼운 Python BLE 스캐너
│   ├── config.json              # Service ID 및 RSSI 감도 설정
│   ├── nearby_scanner.py        # 0xFEF3(Nearby) 및 BLE 신호 실시간 감지기
│   ├── requirements.txt         # 파이썬 의존성 (bleak 등)
│   ├── run_scanner.sh           # 라즈베리파이 원클릭 실행 스크립트
│   └── simulate_nrf_guide.md    # 스마트폰 무료 앱(nRF Connect)으로 즉시 테스트하는 법
├── cpp_google_nearby/           # [고급] Google 공식 Nearby Connections C++ SDK 빌드용
│   ├── setup_rpi_bazel.sh       # Bazel 및 C++ 환경 설치 스크립트
│   ├── src/main.cc              # C++ Nearby Discoverer 소스
│   └── README.md                # C++ 빌드 상세 가이드
├── android_sample/              # 안드로이드 스마트폰 Advertiser 앱 소스코드
│   ├── MainActivity.kt          # startAdvertising 실행 예제
│   ├── AndroidManifest.xml      # 권한 설정
│   └── build.gradle.kts         # 의존성 설정
├── setup_rpi.sh                 # 라즈베리파이 전체 자동 설치 스크립트
└── README.md                    # 본 설명서
```

---

## 🚀 1단계: 지금 PC에서 GitHub에 올리기

새 GitHub 저장소를 생성한 후, 현재 폴더의 터미널(PowerShell 또는 Git Bash)에서 다음 명령어를 순서대로 실행하세요:

```bash
# 1. git 초기화 및 전체 파일 스테이징
git init
git add .
git commit -m "feat: 라즈베리파이 Nearby Connections 디텍터 및 스마트폰 송출 예제 구현"

# 2. 기본 브랜치를 main으로 설정
git branch -M main

# 3. 본인의 GitHub 저장소 주소 연결 (YOUR_USERNAME, REPO_NAME 변경)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# 4. 깃허브에 푸시
git push -u origin main
```

---

## 🍓 2단계: 라즈베리파이에서 다운로드 및 실행

라즈베리파이 터미널(SSH 또는 모니터 터미널)을 열고 실행합니다:

```bash
# 1. 깃허브에서 프로젝트 클론 (다운로드)
git clone https://github.com/YOUR_USERNAME/REPO_NAME.git
cd REPO_NAME

# 2. 실행 권한 부여 및 원클릭 환경 설치
chmod +x setup_rpi.sh python/run_scanner.sh
./setup_rpi.sh

# 3. 스캐너 실행!
cd python
./run_scanner.sh
```

---

## 📱 3단계: 스마트폰으로 신호 보내고 감지 테스트

### 방법 A: 스마트폰 무료 앱으로 1분 만에 테스트 (강력 추천 ⭐)
앱을 직접 빌드하지 않고도 바로 라즈베리파이 동작을 확인할 수 있습니다:
1. 스마트폰 스토어에서 **nRF Connect for Mobile** 앱 설치
2. 앱 실행 ➔ **ADVERTISER** 탭 ➔ **+** 버튼 클릭
3. 데이터 추가: **Service Data** 선택 ➔ UUID에 `FEF3` (Google Nearby 16-bit UUID) 입력
4. 토글 스위치 **ON**
5. 👉 라즈베리파이 화면에 스마트폰의 MAC 주소, 신호 세기(RSSI), 근접 거리가 실시간으로 출력됩니다!
   *(자세한 설정 스크린샷 가이드는 `python/simulate_nrf_guide.md` 참조)*

### 방법 B: 안드로이드 네이티브 앱 제작
- `android_sample/` 폴더의 코드(`MainActivity.kt`)를 Android Studio 프로젝트에 넣어 빌드합니다.
- 스마트폰에서 앱을 켜고 **송출 시작**을 누르면 동일한 `com.atec.mobility.k.hero.nearby.connections.SERVICE_ID`로 Advertising이 시작됩니다.

---

## ⚙️ 설정 커스터마이징 (`python/config.json`)

```json
{
  "service_id": "com.atec.mobility.k.hero.nearby.connections.SERVICE_ID",  // 통신할 서비스 ID
  "rssi_threshold": -85,                        // 신호 감도 필터 (-60: 1m 이내, -85: 약 5~7m)
  "detection_cooldown_seconds": 3,              // 동일 기기 중복 출력 방지 쿨다운 (초)
  "log_to_file": true,                          // detections.log 파일 저장 여부
  "trigger_command": ""                         // 감지 시 실행할 쉘 명령어 (출입문 릴레이 제어 등)
}
```
- 감지 시 릴레이나 모터 구동 스크립트를 연결하려면 `trigger_command`에 `./open_gate.sh` 등을 지정하면 됩니다.

---

## 🛠️ 고급: Google 공식 C++ 라이브러리 사용 시

완전한 구글 공식 C++ 스택으로 빌드하고 싶은 경우:
```bash
cd cpp_google_nearby
chmod +x setup_rpi_bazel.sh
./setup_rpi_bazel.sh
```
자세한 빌드 방법은 `cpp_google_nearby/README.md`를 참고하세요. (Raspberry Pi 4 4GB 이상 권장)
