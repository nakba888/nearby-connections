# 📱 스마트폰 Nearby Connections Advertiser 가이드

이 디렉토리는 안드로이드 스마트폰에서 Google Nearby Connections의 `startAdvertising`을 호출하여 자신의 존재를 주변에 알리는 예제 코드입니다.

---

## 1. 사전 요구 사항
- Android Studio 설치
- 스마트폰 Android 7.0 (API 24) 이상 (BLE 지원 기기)
- Google Play 서비스가 설치된 Android 스마트폰

---

## 2. 프로젝트 적용 방법
1. Android Studio에서 새 Empty Views Activity 프로젝트를 생성합니다.
2. `app/build.gradle.kts`에 `play-services-nearby` 의존성을 추가합니다.
3. `AndroidManifest.xml`에 BLE 및 Nearby 권한을 추가합니다.
4. `MainActivity.kt` 코드를 복사하여 붙여넣습니다.
5. 앱을 스마트폰에 설치 후 **송출 시작** 버튼을 누르면 라즈베리파이에서 스마트폰이 감지됩니다!

---

> 💡 **앱 만들기 전 빠른 테스트**:
> 안드로이드 앱을 빌드하기 전이라도 `python/simulate_nrf_guide.md`를 참고하여 무료 앱인 **nRF Connect**로 즉시 라즈베리파이 수신 테스트를 진행할 수 있습니다.
