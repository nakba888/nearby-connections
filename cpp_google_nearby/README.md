# Google Nearby Connections C++ Discoverer (라즈베리파이)

Google 공식 오픈소스 [google/nearby](https://github.com/google/nearby) C++ 라이브러리를 사용하여 라즈베리파이에서 스마트폰을 탐색(Discoverer)하는 C++ 모듈입니다.

---

## ⚠️ 빌드 전 주의사항

- **하드웨어 권장사양**: Raspberry Pi 4 (4GB 이상) 또는 Raspberry Pi 5.
- Google Nearby C++ 코드는 규모가 크기 때문에 빌드 시 많은 메모리를 소모합니다. 2GB 모델 이하인 경우 스왑(Swap) 메모리를 2GB 이상 늘린 후 빌드하시기 바랍니다.
- **빠른 테스트**가 목적이라면 이 C++ 빌드 대신 상위 폴더의 **`python/nearby_scanner.py`**를 먼저 실행하시는 것을 강력히 권장합니다.

---

## 1. 사전 환경 설치

라즈베리파이에서 다음 스크립트를 실행하여 Bazel 및 필수 라이브러리를 설치합니다:

```bash
chmod +x setup_rpi_bazel.sh
./setup_rpi_bazel.sh
```

---

## 2. 빌드 및 실행

1. **google-nearby 디렉토리로 이동**:
   ```bash
   cd google-nearby
   ```

2. **작성한 Discoverer 소스를 Nearby 저장소로 복사**:
   ```bash
   mkdir -p connections/samples/rpi_discoverer
   cp ../src/main.cc connections/samples/rpi_discoverer/
   cp ../src/BUILD connections/samples/rpi_discoverer/
   ```

3. **Bazel 빌드 실행**:
   ```bash
   bazel build //connections/samples/rpi_discoverer:nearby_discoverer
   ```

4. **실행**:
   ```bash
   ./bazel-bin/connections/samples/rpi_discoverer/nearby_discoverer
   ```
