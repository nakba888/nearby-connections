/**
 * Google Nearby Connections C++ Discoverer & File Receiver (Raspberry Pi)
 * =======================================================================
 * Discovers smartphone Advertiser, establishes connection, accepts incoming
 * files (Payload::Type::kFile / kBytes), and saves them to received_files/ directory.
 */

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <thread>

#include "connections/core.h"
#include "connections/discovery_options.h"
#include "connections/listeners.h"
#include "connections/params.h"
#include "connections/payload.h"
#include "connections/strategy.h"

namespace {
// Target Service ID matching mobile app
constexpr char kServiceId[] = "com.atec.mobility.k.hero.nearby.connections.SERVICE_ID";
constexpr char kDiscovererName[] = "RaspberryPi-Receiver";
constexpr char kSaveDirectory[] = "received_files";
}  // namespace

int main(int argc, char* argv[]) {
  std::cout << "=========================================================\n";
  std::cout << "   Google Nearby Connections Discoverer & File Receiver\n";
  std::cout << "=========================================================\n";
  std::cout << "Target Service ID: " << kServiceId << "\n";
  std::cout << "Discoverer Name:   " << kDiscovererName << "\n";
  std::cout << "Save Directory:    " << kSaveDirectory << "\n";

  // Create destination directory if not existing
  std::filesystem::create_directories(kSaveDirectory);

  // 1. Instantiate Nearby Connections Core
  auto core = std::make_unique<nearby::connections::Core>();

  // 2. Define Payload Listener for receiving files and byte streams
  nearby::connections::PayloadListener payload_listener;

  payload_listener.payload_cb = [](const std::string& endpoint_id,
                                   nearby::connections::Payload payload) {
    std::cout << "\n[PAYLOAD RECEIVED] Endpoint: " << endpoint_id
              << " | Payload ID: " << payload.GetId() << "\n";

    if (payload.GetType() == nearby::connections::Payload::Type::kFile) {
      std::string dest_path = std::string(kSaveDirectory) + "/" +
                              std::to_string(payload.GetId()) + ".file";
      std::cout << "[FILE INCOMING] Type: File | Destination: " << dest_path << "\n";
    } else if (payload.GetType() == nearby::connections::Payload::Type::kBytes) {
      nearby::ByteArray bytes = payload.AsBytes();
      std::string dest_path = std::string(kSaveDirectory) + "/payload_" +
                              std::to_string(payload.GetId()) + ".bin";
      std::ofstream out(dest_path, std::ios::binary);
      if (out.is_open()) {
        out.write(bytes.data(), bytes.size());
        out.close();
        std::cout << "[BYTES SAVED] Saved " << bytes.size()
                  << " bytes to " << dest_path << "\n";
      }
    }
  };

  payload_listener.payload_progress_cb =
      [](const std::string& endpoint_id,
         const nearby::connections::PayloadProgressInfo& info) {
        if (info.status == nearby::connections::PayloadProgressInfo::Status::kInProgress) {
          if (info.total_bytes > 0) {
            double pct = (100.0 * info.bytes_transferred) / info.total_bytes;
            std::cout << "\r[TRANSFER PROGRESS] " << info.bytes_transferred
                      << " / " << info.total_bytes << " bytes (" << static_cast<int>(pct)
                      << "%)" << std::flush;
          }
        } else if (info.status == nearby::connections::PayloadProgressInfo::Status::kSuccess) {
          std::cout << "\n[SUCCESS] File transfer completed for Payload ID: "
                    << info.payload_id << "! Saved to " << kSaveDirectory << "/\n";
        } else if (info.status == nearby::connections::PayloadProgressInfo::Status::kFailure) {
          std::cerr << "\n[ERROR] Payload transfer failed for Payload ID: "
                    << info.payload_id << "\n";
        }
      };

  // 3. Define Connection Lifecycle Listener
  nearby::connections::ConnectionListener connection_listener;

  connection_listener.initiated_cb =
      [&](const std::string& endpoint_id,
          const nearby::connections::ConnectionResponseInfo& info) {
        std::cout << "\n[CONNECTION INITIATED] Endpoint: " << endpoint_id
                  << " | Device: " << info.remote_endpoint_info.data()
                  << " | Auth Token: " << info.authentication_token << "\n";

        // Automatically accept connection to receive payloads
        std::cout << "Accepting connection from " << endpoint_id << "...\n";
        core->AcceptConnection(endpoint_id, payload_listener,
                               [](nearby::connections::Status status) {
                                 if (status.Ok()) {
                                   std::cout << "AcceptConnection sent successfully.\n";
                                 } else {
                                   std::cerr << "Failed to accept connection: "
                                             << status.value << "\n";
                                 }
                               });
      };

  connection_listener.accepted_cb = [](const std::string& endpoint_id) {
    std::cout << "[CONNECTED] Security channel established with: "
              << endpoint_id << "\nReady to receive files via sendPayload()!\n";
  };

  connection_listener.rejected_cb = [](const std::string& endpoint_id,
                                        nearby::connections::Status status) {
    std::cout << "[CONNECTION REJECTED] Endpoint: " << endpoint_id
              << " | Status: " << status.value << "\n";
  };

  connection_listener.disconnected_cb = [](const std::string& endpoint_id) {
    std::cout << "[DISCONNECTED] Endpoint: " << endpoint_id << "\n";
  };

  // 4. Define Discovery Listener
  nearby::connections::DiscoveryListener discovery_listener;

  discovery_listener.endpoint_found_cb =
      [&](const std::string& endpoint_id,
          const nearby::ByteArray& endpoint_info,
          const std::string& service_id) {
        std::string info_str(endpoint_info);
        std::cout << "\n=======================================================\n";
        std::cout << "[TARGET FOUND] Nearby Advertiser Detected!\n";
        std::cout << "• Endpoint ID:   " << endpoint_id << "\n";
        std::cout << "• Endpoint Info: " << info_str << "\n";
        std::cout << "• Service ID:    " << service_id << "\n";
        std::cout << "=======================================================\n";

        // Request Connection
        nearby::connections::ConnectionOptions connection_options;
        connection_options.strategy = nearby::connections::Strategy::kP2pStar;

        std::cout << "Requesting connection to " << endpoint_id << "...\n";
        core->RequestConnection(kDiscovererName, endpoint_id,
                                connection_options, connection_listener,
                                [](nearby::connections::Status status) {
                                  if (!status.Ok()) {
                                    std::cerr << "RequestConnection error: "
                                              << status.value << "\n";
                                  }
                                });
      };

  discovery_listener.endpoint_lost_cb = [](const std::string& endpoint_id) {
    std::cout << "[ENDPOINT LOST] Out of range: " << endpoint_id << "\n";
  };

  // 5. Start Discovery (P2P_STAR, BLE + Wi-Fi)
  nearby::connections::DiscoveryOptions discovery_options;
  discovery_options.strategy = nearby::connections::Strategy::kP2pStar;
  discovery_options.allowed.bluetooth = true;
  discovery_options.allowed.ble = true;
  discovery_options.allowed.wifi_lan = true;

  core->StartDiscovery(kServiceId, discovery_options, discovery_listener,
                       [](nearby::connections::Status status) {
                         if (status.Ok()) {
                           std::cout << "\nDiscovery started successfully.\n";
                           std::cout << "Waiting for smartphone to advertise... (Stop: Ctrl+C)\n\n";
                         } else {
                           std::cerr << "StartDiscovery failed. Status: "
                                     << status.value << "\n";
                         }
                       });

  // Keep thread running
  while (true) {
    std::this_thread::sleep_for(std::chrono::seconds(1));
  }

  // Stop Discovery on exit
  core->StopDiscovery([](nearby::connections::Status) {});
  return 0;
}
