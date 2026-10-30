# 📱 스마트폰으로 Advertising 신호 테스트 가이드 (nRF Connect)

안드로이드 앱을 직접 빌드하기 전에, 스마트폰의 무료 BLE 테스트 앱인 **nRF Connect for Mobile**을 사용해 라즈베리파이의 탐색(Discover) 기능을 즉시 테스트할 수 있습니다.

---

### 1. nRF Connect 앱 설치
- **Android**: Google Play 스토어에서 `nRF Connect for Mobile` (Nordic Semiconductor) 설치
- **iOS**: App Store에서 `nRF Connect for Mobile` 설치

---

### 2. 스마트폰에서 Advertiser(광고 송출) 설정 방법

1. 스마트폰에서 **블루투스**와 **위치(GPS)** 가 켜져 있는지 확인합니다.
2. **nRF Connect** 앱을 실행합니다.
3. 상단 탭에서 **ADVERTISER**를 터치합니다.
4. 우측 하단의 **+** (새 광고 패킷 추가) 버튼을 누릅니다.
5. 설정 화면:
   - **Display name**: `My-Phone-Nearby` (원하는 이름 입력)
   - **Connectable**: 체크(활성화)
6. **ADD DATA** 버튼을 누르고 데이터를 추가합니다:
   - **방법 A: Google Nearby 형식 테스트 (권장)**
     - 데이터 종류: **Service Data** 선택
     - **Service UUID**: `FEF3` 입력 (Google 16-bit UUID)
     - **Data**: `20 1A 2B 3C` 등 원하는 16진수 입력 (예: `20`은 헤더, `1A 2B 3C`는 Service ID 해시값)
   - **방법 B: 커스텀 UUID 테스트**
     - 데이터 종류: **Service UUID (128-bit)** 선택
     - UUID: `12345678-1234-5678-1234-56789abcdef0` 입력 (`config.json`에 등록된 커스텀 UUID)
7. 설정 완료 후 우측 상단의 **SAVE** 버튼을 누릅니다.
8. 생성된 항목 옆의 **토글 스위치를 켜면(ON)** 스마트폰이 즉시 Advertising을 시작합니다!

---

### 3. 라즈베리파이에서 확인하기

라즈베리파이 터미널에서 스캐너를 켜두면:
```bash
./run_scanner.sh
```

스마트폰의 토글을 켜는 순간 라즈베리파이 화면에 다음과 같이 실시간 감지 로그가 뜹니다:
```text
=================================================================
📡 [Google Nearby Connections 신호 감지!]
⏰ 시간: 14:30:15 | 📍 MAC: 5C:XX:XX:XX:XX:XX | 🏷 이름: My-Phone-Nearby
📶 신호세기(RSSI): -58 dBm (매우 가까움 (1m 이내))
📦 Service Data Hex: 201a2b3c
=================================================================
```

스마트폰을 들고 라즈베리파이에 가까이 가거나 멀어지면서 RSSI 수치 변화를 확인할 수 있습니다.
