import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;
import 'package:http/http.dart' as http;

// ============================================================
// medicine_notification_service.dart
// ============================================================

// Model class for a medicine schedule
class MedicineSchedule {
  final int scheduleId;
  final String medicineName;
  final String form;
  final String dosage;
  final String reminderTime; // e.g. "08:00:00"

  MedicineSchedule({
    required this.scheduleId,
    required this.medicineName,
    required this.form,
    required this.dosage,
    required this.reminderTime,
  });

  factory MedicineSchedule.fromJson(Map<String, dynamic> json) {
    return MedicineSchedule(
      scheduleId: json['schedule_id'],
      medicineName: json['medicine_name'],
      form: json['form'],
      dosage: json['dosage'],
      reminderTime: json['reminder_time'],
    );
  }
}

// Core notification service class
class MedicineNotificationService {
  static final MedicineNotificationService _instance =
      MedicineNotificationService._internal();
  factory MedicineNotificationService() => _instance;
  MedicineNotificationService._internal();

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  // Initialize the plugin and timezone data
  Future<void> initialize() async {
    // Initialize timezone database
    tz.initializeTimeZones();

    // --- Android Initialization Settings ---
    const AndroidInitializationSettings androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    // --- iOS / macOS Initialization Settings ---
    const DarwinInitializationSettings iosSettings =
        DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const InitializationSettings initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _plugin.initialize(
      initSettings,
      onDidReceiveNotificationResponse: _onNotificationTapped,
    );

    // Request Android 13+ notification permission
    await _requestAndroidPermission();
  }

  Future<void> _requestAndroidPermission() async {
    final androidPlugin =
        _plugin.resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    await androidPlugin?.requestNotificationsPermission();
  }

  // Callback when user taps notification
  void _onNotificationTapped(NotificationResponse response) {
    debugPrint('Notification tapped with payload: ${response.payload}');
    // Navigate to the medicine detail screen using payload (schedule_id)
  }

  // Schedule a timed notification for a single medicine dose
  Future<void> scheduleMedicineNotification(
      MedicineSchedule schedule) async {
    // Parse reminder time
    final timeParts = schedule.reminderTime.split(':');
    final hour = int.parse(timeParts[0]);
    final minute = int.parse(timeParts[1]);

    // Build a TZDateTime for the next occurrence of this time
    final now = tz.TZDateTime.now(tz.local);
    var scheduledTime = tz.TZDateTime(
      tz.local,
      now.year,
      now.month,
      now.day,
      hour,
      minute,
    );

    // If the time has already passed today, schedule for tomorrow
    if (scheduledTime.isBefore(now)) {
      scheduledTime = scheduledTime.add(const Duration(days: 1));
    }

    // Android notification channel configuration
    const AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
      'medicine_reminders', // Channel ID
      'Medicine Reminders', // Channel Name
      channelDescription: 'Reminders to take your scheduled medicines on time',
      importance: Importance.max,
      priority: Priority.high,
      playSound: true,
      enableVibration: true,
      largeIcon: DrawableResourceAndroidBitmap('@mipmap/ic_launcher'),
      styleInformation: BigTextStyleInformation(''),
    );

    const DarwinNotificationDetails iosDetails = DarwinNotificationDetails(
      sound: 'default',
      badgeNumber: 1,
      interruptionLevel: InterruptionLevel.timeSensitive,
    );

    const NotificationDetails details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    await _plugin.zonedSchedule(
      schedule.scheduleId, // Notification ID = schedule_id for easy identification
      '💊 Medicine Reminder', // Notification Title
      '${schedule.medicineName} • ${schedule.dosage}', // Body
      scheduledTime,
      details,
      payload: schedule.scheduleId.toString(),
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      matchDateTimeComponents: DateTimeComponents.time, // Repeat daily at this exact time
    );

    debugPrint(
        'Scheduled notification for ${schedule.medicineName} at $scheduledTime');
  }

  // Schedule notifications for all patient medicines fetched from the API
  Future<void> scheduleAllFromApi(
      {required String apiBaseUrl, required int userId}) async {
    try {
      final url = Uri.parse('$apiBaseUrl/medicines/$userId');
      final response = await http.get(url);

      if (response.statusCode == 200) {
        final json = jsonDecode(response.body);
        if (json['success'] == true && json['data'] is List) {
          // Cancel all existing notifications to avoid duplicates
          await cancelAll();

          for (final item in json['data']) {
            if (item['is_active'] == 1 || item['is_active'] == true) {
              final schedule = MedicineSchedule.fromJson(item);
              await scheduleMedicineNotification(schedule);
            }
          }

          debugPrint('All medicine notifications scheduled from API.');
        }
      } else {
        debugPrint('Failed to fetch schedules. Status: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error fetching or scheduling notifications: $e');
    }
  }

  // Cancel a specific notification by schedule_id
  Future<void> cancelNotification(int scheduleId) async {
    await _plugin.cancel(scheduleId);
  }

  // Cancel ALL scheduled notifications
  Future<void> cancelAll() async {
    await _plugin.cancelAll();
    debugPrint('All scheduled notifications cancelled.');
  }

  // Show an immediate test notification
  Future<void> showTestNotification({
    required String medicineName,
    required String dosage,
  }) async {
    const AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
      'medicine_reminders',
      'Medicine Reminders',
      channelDescription: 'Test notification for medicine reminder',
      importance: Importance.max,
      priority: Priority.high,
      playSound: true,
      enableVibration: true,
    );

    const NotificationDetails details = NotificationDetails(
      android: androidDetails,
      iOS: DarwinNotificationDetails(sound: 'default'),
    );

    await _plugin.show(
      0, // Notification ID
      '💊 Medicine Reminder',
      '$medicineName • $dosage',
      details,
    );
  }
}

// ============================================================
// main.dart
// ============================================================
void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize the notification service at app startup
  await MedicineNotificationService().initialize();

  // Schedule all notifications from the Flask API
  await MedicineNotificationService().scheduleAllFromApi(
    apiBaseUrl: 'http://10.0.2.2:5000', // Android emulator → localhost
    userId: 1,
  );

  runApp(const AuraMedApp());
}

class AuraMedApp extends StatelessWidget {
  const AuraMedApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AuraMed',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6366F1),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const NotificationDemoScreen(),
    );
  }
}

// Demo screen to test notifications
class NotificationDemoScreen extends StatelessWidget {
  const NotificationDemoScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text(
          'AuraMed Notifications',
          style: TextStyle(color: Color(0xFFF8FAFC), fontWeight: FontWeight.bold),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Info Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white12),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Notification System Active',
                    style: TextStyle(
                        color: Color(0xFF6366F1),
                        fontWeight: FontWeight.bold,
                        fontSize: 16),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'All medicine reminders from the API have been '
                    'scheduled. Notifications will fire automatically at '
                    'the reminder time configured in your schedule.',
                    style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Fire Test Notification Button
            ElevatedButton.icon(
              onPressed: () async {
                await MedicineNotificationService().showTestNotification(
                  medicineName: 'Lisinopril',
                  dosage: '1 Tablet (10mg)',
                );
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Test notification fired!'),
                    backgroundColor: Color(0xFF10B981),
                  ),
                );
              },
              icon: const Icon(Icons.notifications_active),
              label: const Text('Fire Test Notification Now'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6366F1),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
            ),
            const SizedBox(height: 16),

            // Re-Sync with API Button
            OutlinedButton.icon(
              onPressed: () async {
                await MedicineNotificationService().scheduleAllFromApi(
                  apiBaseUrl: 'http://10.0.2.2:5000',
                  userId: 1,
                );
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('All notifications re-synced from API.'),
                    backgroundColor: Color(0xFF6366F1),
                  ),
                );
              },
              icon: const Icon(Icons.sync, color: Color(0xFF6366F1)),
              label: const Text(
                'Re-Sync Notifications from API',
                style: TextStyle(color: Color(0xFF6366F1)),
              ),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: Color(0xFF6366F1)),
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
            ),
            const SizedBox(height: 16),

            // Cancel All Button
            OutlinedButton.icon(
              onPressed: () async {
                await MedicineNotificationService().cancelAll();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('All scheduled notifications cancelled.'),
                    backgroundColor: Color(0xFFEF4444),
                  ),
                );
              },
              icon: const Icon(Icons.notifications_off, color: Color(0xFFEF4444)),
              label: const Text(
                'Cancel All Notifications',
                style: TextStyle(color: Color(0xFFEF4444)),
              ),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: Color(0xFFEF4444)),
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
