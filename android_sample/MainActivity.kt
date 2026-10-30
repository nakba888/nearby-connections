package com.example.nearby.advertiser

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.android.gms.nearby.Nearby
import com.google.android.gms.nearby.connection.*

/**
 * 스마트폰 Nearby Connections Advertiser 예제
 * ===========================================
 * 스마트폰에서 startAdvertising을 호출하여 신호를 방출하고,
 * 라즈베리파이(Discoverer)가 감지할 수 있도록 합니다.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "NearbyAdvertiser"
        // 라즈베리파이와 동일해야 하는 Service ID
        const val SERVICE_ID = "com.example.nearby.detector"
        private const val REQUEST_CODE_PERMISSIONS = 1001
    }

    private lateinit var statusTextView: TextView
    private lateinit var toggleButton: Button
    private var isAdvertising = false

    // 기기 식별용 이름 (예: 사용자 이름이나 차량 번호)
    private val endpointName = "User-Galaxy-Phone"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusTextView = findViewById(R.id.statusTextView)
        toggleButton = findViewById(R.id.toggleButton)

        toggleButton.setOnClickListener {
            if (isAdvertising) {
                stopAdvertising()
            } else {
                checkPermissionsAndStart()
            }
        }
    }

    private fun checkPermissionsAndStart() {
        val permissions = mutableListOf<String>()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_ADVERTISE)
            permissions.add(Manifest.permission.BLUETOOTH_SCAN)
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            permissions.add(Manifest.permission.ACCESS_FINE_LOCATION)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.NEARBY_WIFI_DEVICES)
        }

        val neededPermissions = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (neededPermissions.isEmpty()) {
            startAdvertising()
        } else {
            ActivityCompat.requestPermissions(
                this,
                neededPermissions.toTypedArray(),
                REQUEST_CODE_PERMISSIONS
            )
        }
    }

    private fun startAdvertising() {
        val advertisingOptions = AdvertisingOptions.Builder()
            .setStrategy(Strategy.P2P_STAR) // 1:N 허브-스포크 방식 (라즈베리파이 중심)
            .build()

        Nearby.getConnectionsClient(this)
            .startAdvertising(
                endpointName,
                SERVICE_ID,
                connectionLifecycleCallback,
                advertisingOptions
            )
            .addOnSuccessListener {
                isAdvertising = true
                statusTextView.text = "상태: 송출 중 (Advertising ON)\n라즈베리파이가 감지할 수 있습니다."
                toggleButton.text = "송출 중지"
                Toast.makeText(this, "Nearby Advertising 시작됨", Toast.LENGTH_SHORT).show()
                Log.d(TAG, "Advertising started successfully")
            }
            .addOnFailureListener { e ->
                statusTextView.text = "상태: 시작 실패 (${e.localizedMessage})"
                Log.e(TAG, "Advertising failed to start", e)
                Toast.makeText(this, "시작 실패: ${e.message}", Toast.LENGTH_LONG).show()
            }
    }

    private fun stopAdvertising() {
        Nearby.getConnectionsClient(this).stopAdvertising()
        isAdvertising = false
        statusTextView.text = "상태: 중지됨 (Advertising OFF)"
        toggleButton.text = "송출 시작"
        Toast.makeText(this, "Nearby Advertising 중지됨", Toast.LENGTH_SHORT).show()
    }

    private val connectionLifecycleCallback = object : ConnectionLifecycleCallback() {
        override fun onConnectionInitiated(endpointId: String, connectionInfo: ConnectionInfo) {
            Log.d(TAG, "연결 요청 감지: $endpointId (${connectionInfo.endpointName})")
            statusTextView.text = "연결 요청 감지됨: ${connectionInfo.endpointName}"

            // 라즈베리파이 연결 요청 자동 수락
            Nearby.getConnectionsClient(this@MainActivity)
                .acceptConnection(endpointId, payloadCallback)
        }

        override fun onConnectionResult(endpointId: String, result: ConnectionResolution) {
            when (result.status.statusCode) {
                ConnectionsStatusCodes.STATUS_OK -> {
                    statusTextView.text = "라즈베리파이와 연결 성공! ($endpointId)"
                    Log.d(TAG, "Connected to $endpointId")
                }
                ConnectionsStatusCodes.STATUS_CONNECTION_REJECTED -> {
                    statusTextView.text = "연결 거절됨"
                }
                else -> {
                    statusTextView.text = "연결 실패: ${result.status.statusMessage}"
                }
            }
        }

        override fun onDisconnected(endpointId: String) {
            statusTextView.text = "라즈베리파이 연결 해제됨"
            Log.d(TAG, "Disconnected from $endpointId")
        }
    }

    private val payloadCallback = object : PayloadCallback() {
        override fun onPayloadReceived(endpointId: String, payload: Payload) {
            if (payload.type == Payload.Type.BYTES) {
                val data = String(payload.asBytes() ?: ByteArray(0))
                Log.d(TAG, "수신 데이터: $data")
                Toast.makeText(this@MainActivity, "수신: $data", Toast.LENGTH_SHORT).show()
            }
        }

        override fun onPayloadTransferUpdate(endpointId: String, update: PayloadTransferUpdate) {}
    }

    override fun onDestroy() {
        super.onDestroy()
        stopAdvertising()
    }
}
