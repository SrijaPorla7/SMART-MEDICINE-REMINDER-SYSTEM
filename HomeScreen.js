import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  SafeAreaView,
  StatusBar,
  Alert
} from 'react-native';

// API Configuration - Replace with your actual local/hosted Flask API URL
// In React Native android simulator, 10.0.2.2 points to localhost. On iOS, use local IP.
const API_BASE_URL = 'http://10.0.2.2:5000';
const USER_ID = 1; // Testing with John Doe (Patient 1)

export default function HomeScreen() {
  const [loading, setLoading] = useState(true);
  const [medicines, setMedicines] = useState([]);
  const [loggedDoses, setLoggedDoses] = useState({}); // Stores schedule_id -> taken status mappings

  useEffect(() => {
    fetchSchedulesAndLogs();
  }, []);

  const fetchSchedulesAndLogs = async () => {
    setLoading(true);
    try {
      // 1. Fetch patient's active schedules
      const scheduleRes = await fetch(`${API_BASE_URL}/medicines/${USER_ID}`);
      const scheduleJson = await scheduleRes.json();

      if (!scheduleJson.success) {
        Alert.alert('Error', 'Failed to retrieve medicine schedules.');
        setLoading(false);
        return;
      }

      // 2. Fetch recent compliance logs to check if today's dose is already taken
      const reportRes = await fetch(`${API_BASE_URL}/adherence-report/${USER_ID}`);
      const reportJson = await reportRes.json();

      const todayStr = new Date().toISOString().split('T')[0];
      const initialLoggedState = {};

      if (reportJson.success && reportJson.data.recent_logs) {
        reportJson.data.recent_logs.forEach(log => {
          // If the log is for today and marked taken, set true
          const logDate = log.scheduled_datetime.split('T')[0];
          if (logDate === todayStr && log.status === 'Taken') {
            initialLoggedState[log.schedule_id] = true;
          }
        });
      }

      setMedicines(scheduleJson.data.filter(s => s.is_active));
      setLoggedDoses(initialLoggedState);
    } catch (error) {
      console.error(error);
      Alert.alert('Connection Error', 'Unable to reach the server. Please check configurations.');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsTaken = async (scheduleId, reminderTime, medicineName) => {
    const todayStr = new Date().toISOString().split('T')[0];
    const scheduledDatetime = `${todayStr} ${reminderTime}`; // Format: YYYY-MM-DD HH:MM:SS

    try {
      const response = await fetch(`${API_BASE_URL}/mark-taken`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          schedule_id: scheduleId,
          scheduled_datetime: scheduledDatetime,
          status: 'Taken',
        }),
      });

      const json = await response.json();

      if (json.success) {
        // Update local state to reflect checkmark
        setLoggedDoses(prev => ({
          ...prev,
          [scheduleId]: true
        }));
        Alert.alert('Success', `Logged dose for ${medicineName}!`);
      } else {
        Alert.alert('Error', json.message || 'Could not log dose.');
      }
    } catch (error) {
      console.error(error);
      Alert.alert('Error', 'Network request failed.');
    }
  };

  // Render medication card item
  const renderMedicineItem = ({ item }) => {
    const isTaken = !!loggedDoses[item.schedule_id];

    return (
      <View style={styles.card}>
        <View style={styles.cardLeft}>
          <View style={styles.iconPlaceholder}>
            <Text style={styles.pillEmoji}>{item.form === 'Syrup' ? '🧪' : '💊'}</Text>
          </View>
          <View style={styles.infoColumn}>
            <Text style={styles.medName}>{item.medicine_name}</Text>
            <Text style={styles.medDetails}>
              {item.dosage} • {formatTime12h(item.reminder_time)}
            </Text>
            {item.special_instructions && (
              <Text style={styles.instructions} numberOfLines={1}>
                ⚠️ {item.special_instructions}
              </Text>
            )}
          </View>
        </View>

        <View style={styles.cardRight}>
          {isTaken ? (
            <View style={styles.checkmarkContainer}>
              <Text style={styles.checkmarkIcon}>✓</Text>
            </View>
          ) : (
            <TouchableOpacity
              style={styles.btnTaken}
              onPress={() => handleMarkAsTaken(item.schedule_id, item.reminder_time, item.medicine_name)}
            >
              <Text style={styles.btnText}>Take</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    );
  };

  // Helper: format standard 24h string (e.g. 14:00:00) into 12h time
  const formatTime12h = (timeStr) => {
    const [hours, minutes] = timeStr.split(':');
    const hr = parseInt(hours);
    const ampm = hr >= 12 ? 'PM' : 'AM';
    const formattedHr = hr % 12 || 12;
    return `${formattedHr}:${minutes} ${ampm}`;
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#0F172A" />
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>AuraMed App</Text>
            <Text style={styles.headerSubtitle}>Today's Medication checklist</Text>
          </View>
          <TouchableOpacity onPress={fetchSchedulesAndLogs} style={styles.refreshButton}>
            <Text style={styles.refreshText}>↻</Text>
          </TouchableOpacity>
        </View>

        {/* List Content */}
        {loading ? (
          <View style={styles.centerContainer}>
            <ActivityIndicator size="large" color="#6366F1" />
            <Text style={styles.loadingText}>Fetching schedules...</Text>
          </View>
        ) : medicines.length === 0 ? (
          <View style={styles.centerContainer}>
            <Text style={styles.emptyIcon}>🎉</Text>
            <Text style={styles.emptyText}>All clear! No medications due.</Text>
          </View>
        ) : (
          <FlatList
            data={medicines}
            keyExtractor={(item) => item.schedule_id.toString()}
            renderItem={renderMedicineItem}
            contentContainerStyle={styles.listContainer}
          />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  container: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 10,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.08)',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  headerSubtitle: {
    fontSize: 13,
    color: '#94A3B8',
    marginTop: 4,
  },
  refreshButton: {
    padding: 8,
  },
  refreshText: {
    fontSize: 26,
    color: '#6366F1',
    fontWeight: 'bold',
  },
  listContainer: {
    paddingBottom: 20,
  },
  card: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    borderRadius: 12,
    padding: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  iconPlaceholder: {
    width: 44,
    height: 44,
    borderRadius: 8,
    backgroundColor: '#334155',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  pillEmoji: {
    fontSize: 20,
  },
  infoColumn: {
    flex: 1,
  },
  medName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  medDetails: {
    fontSize: 13,
    color: '#94A3B8',
    marginTop: 4,
  },
  instructions: {
    fontSize: 11,
    color: '#F59E0B',
    marginTop: 4,
  },
  cardRight: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  btnTaken: {
    backgroundColor: '#6366F1',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
  },
  btnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  checkmarkContainer: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderWidth: 1.5,
    borderColor: '#10B981',
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkmarkIcon: {
    color: '#10B981',
    fontSize: 18,
    fontWeight: 'bold',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    color: '#94A3B8',
    fontSize: 14,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  emptyText: {
    color: '#94A3B8',
    fontSize: 14,
    textAlign: 'center',
  },
});
