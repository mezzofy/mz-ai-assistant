import React from 'react';
import {View, Text, TouchableOpacity, StyleSheet, ScrollView} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {useTheme} from '../hooks/useTheme';

type Props = {
  navigation: any;
};

export const PrivacySecurityScreen: React.FC<Props> = ({navigation}) => {
  const colors = useTheme();

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      {/* Header */}
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <TouchableOpacity onPress={() => navigation.goBack()} activeOpacity={0.7} style={styles.backBtn}>
          <Icon name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.title, {color: colors.text}]}>Privacy & Security</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView style={styles.list}>
        <View style={[styles.group, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          {/* Change Password */}
          <TouchableOpacity
            onPress={() => navigation.navigate('ChangePassword')}
            style={styles.row}
            activeOpacity={0.7}>
            <View style={[styles.rowIcon, {backgroundColor: colors.accentSoft}]}>
              <Icon name="shield-checkmark-outline" size={18} color={colors.accent} />
            </View>
            <Text style={[styles.rowLabel, {color: colors.text}]}>Change Password</Text>
            <Icon name="chevron-forward" size={16} color={colors.textDim} />
          </TouchableOpacity>

          {/* Two-Factor Authentication placeholder */}
          <View style={[styles.row, {borderBottomWidth: 0}]}>
            <View style={[styles.rowIcon, {backgroundColor: colors.surface}]}>
              <Icon name="phone-portrait-outline" size={18} color={colors.textMuted} />
            </View>
            <Text style={[styles.rowLabel, {color: colors.text}]}>Two-Factor Authentication</Text>
            <View style={[styles.badge, {backgroundColor: colors.surface, borderColor: colors.border}]}>
              <Text style={[styles.badgeText, {color: colors.textDim}]}>Coming Soon</Text>
            </View>
          </View>
        </View>

        <Text style={[styles.sectionNote, {color: colors.textDim}]}>
          Keep your account secure by using a strong, unique password and enabling two-factor authentication when available.
        </Text>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: {width: 36, height: 36, alignItems: 'center', justifyContent: 'center'},
  title: {fontSize: 17, fontWeight: '700'},
  list: {flex: 1, paddingHorizontal: 16, paddingTop: 24},
  group: {borderRadius: 14, overflow: 'hidden', marginBottom: 12, borderWidth: 1},
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    padding: 14, paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: 'rgba(255,255,255,0.08)',
  },
  rowIcon: {width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center'},
  rowLabel: {flex: 1, fontSize: 14, fontWeight: '500'},
  badge: {
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 6, borderWidth: 1,
  },
  badgeText: {fontSize: 11, fontWeight: '600'},
  sectionNote: {fontSize: 13, lineHeight: 20, paddingHorizontal: 4, marginBottom: 24},
});
