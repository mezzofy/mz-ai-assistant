import React, {useEffect, useRef, useState} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform,
  Modal, Dimensions,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';
import {applyLeave, getLeaveTypes, type LeaveType} from '../api/hrApi';

// ── Inline Date Picker (no external deps) ─────────────────────────────────────

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const ITEM_H = 44;
const VISIBLE = 5; // items visible in the wheel
const now = new Date();

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

type WheelProps = {
  items: string[];
  selectedIndex: number;
  onSelect: (i: number) => void;
  colors: ReturnType<typeof useTheme>;
};

const Wheel: React.FC<WheelProps> = ({items, selectedIndex, onSelect, colors}) => {
  const scrollRef = useRef<ScrollView>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({y: selectedIndex * ITEM_H, animated: false});
  }, [selectedIndex]);

  return (
    <View style={{height: ITEM_H * VISIBLE, overflow: 'hidden', flex: 1}}>
      {/* highlight band */}
      <View style={[wheelStyles.band, {
        top: ITEM_H * Math.floor(VISIBLE / 2),
        borderTopColor: colors.accent + '60',
        borderBottomColor: colors.accent + '60',
      }]} />
      <ScrollView
        ref={scrollRef}
        showsVerticalScrollIndicator={false}
        snapToInterval={ITEM_H}
        decelerationRate="fast"
        contentContainerStyle={{paddingVertical: ITEM_H * Math.floor(VISIBLE / 2)}}
        onMomentumScrollEnd={e => {
          const idx = Math.round(e.nativeEvent.contentOffset.y / ITEM_H);
          onSelect(Math.max(0, Math.min(idx, items.length - 1)));
        }}>
        {items.map((label, i) => (
          <TouchableOpacity
            key={i}
            onPress={() => {
              onSelect(i);
              scrollRef.current?.scrollTo({y: i * ITEM_H, animated: true});
            }}
            style={wheelStyles.item}>
            <Text style={[
              wheelStyles.itemText,
              {color: i === selectedIndex ? colors.text : colors.textDim,
               fontWeight: i === selectedIndex ? '700' : '400',
               fontSize: i === selectedIndex ? 17 : 14},
            ]}>
              {label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
};

const wheelStyles = StyleSheet.create({
  band: {
    position: 'absolute', left: 0, right: 0, height: ITEM_H,
    borderTopWidth: 1, borderBottomWidth: 1, zIndex: 1, pointerEvents: 'none',
  },
  item: {height: ITEM_H, alignItems: 'center', justifyContent: 'center'},
  itemText: {textAlign: 'center'},
});

type DatePickerProps = {
  visible: boolean;
  value: string;          // YYYY-MM-DD or ''
  onConfirm: (d: string) => void;
  onCancel: () => void;
  colors: ReturnType<typeof useTheme>;
};

const DatePickerModal: React.FC<DatePickerProps> = ({visible, value, onConfirm, onCancel, colors}) => {
  const [selYear, setSelYear] = useState(now.getFullYear());
  const [selMonth, setSelMonth] = useState(now.getMonth() + 1);   // 1-12
  const [selDay, setSelDay] = useState(now.getDate());

  useEffect(() => {
    if (!visible) { return; }
    if (value && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const [y, m, d] = value.split('-').map(Number);
      setSelYear(y); setSelMonth(m); setSelDay(d);
    } else {
      setSelYear(now.getFullYear()); setSelMonth(now.getMonth() + 1); setSelDay(now.getDate());
    }
  }, [visible, value]);

  const baseYear = now.getFullYear();
  const years  = Array.from({length: 6}, (_, i) => String(baseYear + i));
  const months = MONTHS.map((m, i) => `${String(i + 1).padStart(2, '0')} ${m}`);
  const totalDays = daysInMonth(selYear, selMonth);
  const days = Array.from({length: totalDays}, (_, i) => String(i + 1).padStart(2, '0'));

  const yearIdx  = years.findIndex(y => Number(y) === selYear);
  const monthIdx = selMonth - 1;
  const dayIdx   = Math.min(selDay - 1, totalDays - 1);

  const handleConfirm = () => {
    const safeDay = Math.min(selDay, daysInMonth(selYear, selMonth));
    onConfirm(
      `${selYear}-${String(selMonth).padStart(2, '0')}-${String(safeDay).padStart(2, '0')}`,
    );
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onCancel}>
      <TouchableOpacity style={pickerStyles.overlay} activeOpacity={1} onPress={onCancel} />
      <View style={[pickerStyles.sheet, {backgroundColor: colors.surfaceLight, borderTopColor: colors.border}]}>
        {/* Title bar */}
        <View style={[pickerStyles.titleBar, {borderBottomColor: colors.border}]}>
          <TouchableOpacity onPress={onCancel} style={pickerStyles.titleBtn}>
            <Text style={{color: colors.textMuted, fontSize: 15}}>Cancel</Text>
          </TouchableOpacity>
          <Text style={[pickerStyles.titleText, {color: colors.text}]}>Select Date</Text>
          <TouchableOpacity onPress={handleConfirm} style={pickerStyles.titleBtn}>
            <Text style={{color: colors.accent, fontSize: 15, fontWeight: '700'}}>Done</Text>
          </TouchableOpacity>
        </View>
        {/* Wheels */}
        <View style={pickerStyles.wheelsRow}>
          <Wheel
            items={years}
            selectedIndex={Math.max(0, yearIdx)}
            onSelect={i => setSelYear(Number(years[i]))}
            colors={colors}
          />
          <Wheel
            items={months}
            selectedIndex={monthIdx}
            onSelect={i => setSelMonth(i + 1)}
            colors={colors}
          />
          <Wheel
            items={days}
            selectedIndex={dayIdx}
            onSelect={i => setSelDay(i + 1)}
            colors={colors}
          />
        </View>
      </View>
    </Modal>
  );
};

const pickerStyles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  sheet: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    borderTopWidth: 1, paddingBottom: 36,
  },
  titleBar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  titleBtn: {padding: 4, minWidth: 60},
  titleText: {fontSize: 16, fontWeight: '600'},
  wheelsRow: {flexDirection: 'row', paddingHorizontal: 8, paddingTop: 8},
});

// ── Date Input Field ───────────────────────────────────────────────────────────

type DateFieldProps = {
  label: string;
  value: string;
  onPick: () => void;
  colors: ReturnType<typeof useTheme>;
};

const DateField: React.FC<DateFieldProps> = ({label, value, onPick, colors}) => (
  <>
    <Text style={[fieldStyles.label, {color: colors.textMuted}]}>
      {label} <Text style={{color: colors.accent}}>*</Text>
    </Text>
    <TouchableOpacity
      onPress={onPick}
      activeOpacity={0.8}
      style={[fieldStyles.wrap, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
      <Icon name="calendar-outline" size={16} color={colors.textDim} style={{paddingLeft: 14}} />
      <Text style={[fieldStyles.text, {color: value ? colors.text : colors.textDim}]}>
        {value || 'Select date'}
      </Text>
      <Icon name="chevron-down-outline" size={14} color={colors.textDim} style={{paddingRight: 14}} />
    </TouchableOpacity>
  </>
);

const fieldStyles = StyleSheet.create({
  label: {fontSize: 12, fontWeight: '600', marginBottom: 8, marginTop: 4, textTransform: 'uppercase', letterSpacing: 0.5},
  wrap: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderRadius: 12, borderWidth: 1, marginBottom: 16, height: 50,
  },
  text: {flex: 1, fontSize: 15, paddingLeft: 2},
});

// ── Screen ─────────────────────────────────────────────────────────────────────

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
  const [pickerTarget, setPickerTarget] = useState<'start' | 'end' | null>(null);

  useEffect(() => {
    getLeaveTypes()
      .then(res => {
        if (res?.data?.leave_types) {
          setLeaveTypes(res.data.leave_types);
          if (res.data.leave_types.length > 0) { setSelectedType(res.data.leave_types[0].id); }
        }
      })
      .catch(() => {})
      .finally(() => setTypesLoading(false));
  }, []);

  // Auto-compute total days when both dates are set
  useEffect(() => {
    if (startDate && endDate &&
        /^\d{4}-\d{2}-\d{2}$/.test(startDate) &&
        /^\d{4}-\d{2}-\d{2}$/.test(endDate)) {
      const start = new Date(startDate);
      const end   = new Date(endDate);
      if (end >= start) {
        const diff = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
        setTotalDays(String(diff));
      }
    }
  }, [startDate, endDate]);

  const handleSubmit = async () => {
    setError(null);
    if (!selectedType) { setError('Please select a leave type.'); return; }
    if (!startDate) { setError('Please select a start date.'); return; }
    if (!endDate)   { setError('Please select an end date.'); return; }
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

  const pickerValue = pickerTarget === 'start' ? startDate : endDate;

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
        <DateField
          label="Start Date"
          value={startDate}
          onPick={() => setPickerTarget('start')}
          colors={colors}
        />

        {/* End Date */}
        <DateField
          label="End Date"
          value={endDate}
          onPick={() => setPickerTarget('end')}
          colors={colors}
        />

        {/* Total Days (auto-computed, still editable) */}
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

      {/* Date picker modal */}
      <DatePickerModal
        visible={pickerTarget !== null}
        value={pickerValue}
        onConfirm={d => {
          if (pickerTarget === 'start') { setStartDate(d); }
          else { setEndDate(d); }
          setPickerTarget(null);
        }}
        onCancel={() => setPickerTarget(null)}
        colors={colors}
      />
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
  typeChip: {paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1},
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
  successWrap: {flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 32},
  iconCircle: {width: 80, height: 80, borderRadius: 24, alignItems: 'center', justifyContent: 'center', marginBottom: 24},
  successTitle: {fontSize: 22, fontWeight: '800', marginBottom: 12},
  successSub: {fontSize: 14, textAlign: 'center', lineHeight: 22, marginBottom: 40},
  doneBtn: {width: '100%', padding: 16, borderRadius: 14, alignItems: 'center'},
  doneBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
});
