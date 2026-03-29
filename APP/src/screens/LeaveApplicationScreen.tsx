import React, {useEffect, useState} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {applyLeave, getLeaveTypes, type LeaveType} from '../api/hrApi';

type Props = {
  navigation: any;
  route: {params?: {employee_id?: string}};
};

export const LeaveApplicationScreen: React.FC<Props> = ({navigation}) => {
  const colors = useTheme();
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([]);
  const [selectedType, setSelectedType] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [totalDays, setTotalDays] = useState('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [typesLoading, setTypesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    getLeaveTypes()
      .then(res => {
        if (res?.data?.leave_types) {
          setLeaveTypes(res.data.leave_types);
          if (res.data.leave_types.length > 0) {
            setSelectedType(res.data.leave_types[0].id);
          }
        }
      })
      .catch(() => {/* ignore */})
      .finally(() => setTypesLoading(false));
  }, []);

  const handleSubmit = async () => {
    setError(null);
    if (!selectedType) { setError('Please select a leave type.'); return; }
    if (!startDate.match(/^\d{4}-\d{2}-\d{2}$/)) { setError('Start date must be YYYY-MM-DD.'); return; }
    if (!endDate.match(/^\d{4}-\d{2}-\d{2}$/)) { setError('End date must be YYYY-MM-DD.'); return; }
    const days = parseFloat(totalDays);
    if (!totalDays || isNaN(days) || days <= 0) { setError('Enter valid number of days.'); return; }

    setLoading(true);
    try {
      await applyLeave({
        leave_type_id: selectedType,
        start_date: startDate,
        end_date: endDate,
        total_days: days,
        reason: reason.trim() || undefined,
      });
      setSuccess(true);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to submit leave application.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <View style={[styles.container, {backgroundColor: colors.primary}]}>
        <View style={styles.successWrap}>
          <View style={[styles.iconCircle, {backgroundColor: colors.success + '20'}]}>
            <Icon name="checkmark-circle" size={40} color={colors.success} />
          </View>
          <Text style={[styles.successTitle, {color: colors.text}]}>Application Submitted</Text>
          <Text style={[styles.successSub, {color: colors.textMuted}]}>
            Your leave request has been submitted and is pending approval.
          </Text>
          <TouchableOpacity
            onPress={() => navigation.goBack()}
            activeOpacity={0.8}
            style={[styles.doneBtn, {backgroundColor: colors.accent}]}>
            <Text style={styles.doneBtnText}>Done</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={[styles.container, {backgroundColor: colors.primary}]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {/* Header */}
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Icon name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, {color: colors.text}]}>Apply Leave</Text>
        <View style={{width: 30}} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled">

        {/* Leave Type */}
        <Text style={[styles.label, {color: colors.textMuted}]}>
          Leave Type <Text style={{color: colors.accent}}>*</Text>
        </Text>
        {typesLoading ? (
          <ActivityIndicator color={colors.accent} style={{marginBottom: 16}} />
        ) : (
          <View style={styles.typeRow}>
            {leaveTypes.map(lt => (
              <TouchableOpacity
                key={lt.id}
                onPress={() => setSelectedType(lt.id)}
                activeOpacity={0.8}
                style={[
                  styles.typeChip,
                  {
                    backgroundColor: selectedType === lt.id ? colors.accent : colors.surfaceLight,
                    borderColor: selectedType === lt.id ? colors.accent : colors.border,
                  },
                ]}>
                <Text style={[
                  styles.typeChipText,
                  {color: selectedType === lt.id ? '#fff' : colors.textMuted},
                ]}>
                  {lt.name}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Start Date */}
        <Text style={[styles.label, {color: colors.textMuted}]}>
          Start Date <Text style={{color: colors.accent}}>*</Text>
        </Text>
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="calendar-outline" size={16} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={startDate}
            onChangeText={setStartDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={colors.textDim}
            style={[styles.input, {color: colors.text}]}
          />
        </View>

        {/* End Date */}
        <Text style={[styles.label, {color: colors.textMuted}]}>
          End Date <Text style={{color: colors.accent}}>*</Text>
        </Text>
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="calendar-outline" size={16} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={endDate}
            onChangeText={setEndDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={colors.textDim}
            style={[styles.input, {color: colors.text}]}
          />
        </View>

        {/* Total Days */}
        <Text style={[styles.label, {color: colors.textMuted}]}>
          Number of Days <Text style={{color: colors.accent}}>*</Text>
        </Text>
        <View style={[styles.inputWrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="time-outline" size={16} color={colors.textDim} style={styles.inputIcon} />
          <TextInput
            value={totalDays}
            onChangeText={setTotalDays}
            placeholder="e.g. 2 or 0.5 for half day"
            placeholderTextColor={colors.textDim}
            keyboardType="decimal-pad"
            style={[styles.input, {color: colors.text}]}
          />
        </View>

        {/* Reason */}
        <Text style={[styles.label, {color: colors.textMuted}]}>Reason (optional)</Text>
        <View style={[
          styles.inputWrap,
          {backgroundColor: colors.surfaceLight, borderColor: colors.border, alignItems: 'flex-start'},
        ]}>
          <TextInput
            value={reason}
            onChangeText={setReason}
            placeholder="Add a reason for your leave..."
            placeholderTextColor={colors.textDim}
            multiline
            numberOfLines={3}
            style={[styles.input, styles.textArea, {color: colors.text}]}
          />
        </View>

        {error ? (
          <View style={[styles.errorWrap, {backgroundColor: colors.danger + '18', borderColor: colors.danger + '33'}]}>
            <Icon name="alert-circle-outline" size={15} color={colors.danger} />
            <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
          </View>
        ) : null}

        <TouchableOpacity
          onPress={handleSubmit}
          disabled={loading}
          activeOpacity={0.8}
          style={[
            styles.submitBtn,
            {backgroundColor: colors.accent, shadowColor: colors.accent},
            loading && {backgroundColor: colors.textDim, shadowOpacity: 0},
          ]}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitBtnText}>Submit Application</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1,
  },
  backBtn: {padding: 4},
  headerTitle: {fontSize: 18, fontWeight: '700'},
  scroll: {flex: 1},
  scrollContent: {padding: 20, paddingBottom: 40},
  label: {fontSize: 12, fontWeight: '600', marginBottom: 8, marginTop: 4, textTransform: 'uppercase', letterSpacing: 0.5},
  typeRow: {flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 20},
  typeChip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1,
  },
  typeChipText: {fontSize: 13, fontWeight: '500'},
  inputWrap: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: 12, borderWidth: 1, marginBottom: 16,
  },
  inputIcon: {paddingLeft: 14},
  input: {flex: 1, padding: 14, paddingLeft: 10, fontSize: 14},
  textArea: {minHeight: 80, textAlignVertical: 'top'},
  errorWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    padding: 12, borderRadius: 10, borderWidth: 1, marginBottom: 12,
  },
  errorText: {flex: 1, fontSize: 13},
  submitBtn: {
    padding: 16, borderRadius: 14, alignItems: 'center',
    shadowOffset: {width: 0, height: 4}, shadowOpacity: 0.4, shadowRadius: 20, elevation: 8,
  },
  submitBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
  // Success state
  successWrap: {flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 32},
  iconCircle: {
    width: 80, height: 80, borderRadius: 24,
    alignItems: 'center', justifyContent: 'center', marginBottom: 24,
  },
  successTitle: {fontSize: 22, fontWeight: '800', marginBottom: 12},
  successSub: {fontSize: 14, textAlign: 'center', lineHeight: 22, marginBottom: 40},
  doneBtn: {
    width: '100%', padding: 16, borderRadius: 14, alignItems: 'center',
  },
  doneBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
});
