/**
 * Google Nearby Connections C++ Discoverer for Linux / Raspberry Pi
 * =================================================================
 * Google의 공식 오픈소스 Nearby Connections C++ SDK를 사용하여
 * 스마트폰(Advertiser)의 접속 신호를 탐색(Discover)하는 C++ 구현 예제입니다.
 */

#include <chrono>
#include <iostream>
#include <memory>
#include <string>
#include <thread>

#include "connections/core.h"
#include "connections/discovery_options.h"
#include "connections/listeners.h"
#include "connections/params.h"
#include "connections/strategy.h"

namespace {
// 스마트폰 앱과 동일하게 지정해야 하는 Service ID
constexpr char kServiceId[] = "com.example.nearby.detector";
constexpr char kDiscovererName[] = "RaspberryPi-Gate";
}  // namespace

int main(int argc, char* argv[]) {
  std::cout << "=========================================================\n";
  std::cout << "   Google Nearby Connections C++ Discoverer (Raspberry Pi)\n";
  std::cout << "=========================================================\n";
  std::cout << "• Service ID: " << kServiceId << "\n";
  std::cout << "• Discoverer Name: " << kDiscovererName << "\n";
  std::cout << "초기화 및 스마트폰 탐색을 시작합니다...\n\n";

  // 1. Nearby Connections Core 인스턴스 생성
  auto core = std::make_unique<nearby::connections::Core>();

  // 2. 연결 라이프사이클 콜백 정의
  nearby::connections::ConnectionListener connection_listener;
  connection_listener.initiated_cb = [](const std::string& endpoint_id,
                                        const nearby::connections::ConnectionResponseInfo& info) {
    std::cout << "\n🤝 [연결 요청 감지!] Endpoint ID: " << endpoint_id
              << " | 기기 인증 토큰: " << info.authentication_token << "\n";
  };
  connection_listener.accepted_cb = [](const std::string& endpoint_id) {
    std::cout << "✅ [연결 성공!] 스마트폰과 보안 채널이 연결되었습니다: "
              << endpoint_id << "\n";
  };
  connection_listener.rejected_cb = [](const std::string& endpoint_id,
                                        nearby::connections::Status status) {
    std::cout << "❌ [연결 거절됨] Endpoint: " << endpoint_id
              << " (Status: " << status.value << ")\n";
  };
  connection_listener.disconnected_cb = [](const std::string& endpoint_id) {
    std::cout << "🔌 [연결 해제됨] Endpoint: " << endpoint_id << "\n";
  };

  // 3. 탐색(Discovery) 리스너 정의
  nearby::connections::DiscoveryListener discovery_listener;
  discovery_listener.endpoint_found_cb =
      [&](const std::string& endpoint_id,
          const nearby::ByteArray& endpoint_info,
          const std::string& service_id) {
        std::string info_str(endpoint_info);
        std::cout << "\n=======================================================\n";
        std::cout << "🎯 [스마트폰 발견!] Nearby Advertiser 감지됨!\n";
        std::cout << "• Endpoint ID: " << endpoint_id << "\n";
        std::cout << "• Endpoint Info (기기명): " << info_str << "\n";
        std::cout << "• Service ID: " << service_id << "\n";
        std::cout << "=======================================================\n";

        // 발견된 스마트폰에 연결 요청 (필요한 경우 자동 연결 시도)
        nearby::connections::ConnectionOptions connection_options;
        connection_options.strategy = nearby::connections::Strategy::kP2pStar;

        std::cout << "스마트폰(" << endpoint_id << ")에 연결을 요청합니다...\n";
        core->RequestConnection(kDiscovererName, endpoint_id,
                                connection_options, connection_listener,
                                [](nearby::connections::Status status) {
                                  if (!status.Ok()) {
                                    std::cerr << "연결 요청 실패: "
                                              << status.value << "\n";
                                  }
                                });
      };

  discovery_listener.endpoint_lost_cb = [](const std::string& endpoint_id) {
    std::cout << "💨 [스마트폰 이탈] 신호가 끊어졌습니다: " << endpoint_id << "\n";
  };

  // 4. 탐색 옵션 설정 (P2P_STAR 전략, BLE/Wi-Fi 탐색)
  nearby::connections::DiscoveryOptions discovery_options;
  discovery_options.strategy = nearby::connections::Strategy::kP2pStar;
  discovery_options.allowed.bluetooth = true;
  discovery_options.allowed.ble = true;
  discovery_options.allowed.wifi_lan = true;

  // 5. 탐색 시작
  core->StartDiscovery(kServiceId, discovery_options, discovery_listener,
                       [](nearby::connections::Status status) {
                         if (status.Ok()) {
                           std::cout << "🚀 탐색이 정상적으로 시작되었습니다.\n";
                           std::cout << "스마트폰에서 Advertising을 켜주세요. (종료: Ctrl+C)\n\n";
                         } else {
                           std::cerr << "❌ 탐색 시작 실패. Status: "
                                     << status.value << "\n";
                         }
                       });

  // 메인 스레드 유지
  while (true) {
    std::this_thread::sleep_for(std::chrono::seconds(1));
  }

  // 6. 종료 시 탐색 중지
  core->StopDiscovery([](nearby::connections::Status) {});
  return 0;
}
