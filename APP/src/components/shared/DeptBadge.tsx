import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import {BRAND} from '../../utils/theme';

type Props = {
  dept: string;
  compact?: boolean;
};

export const DeptBadge: React.FC<Props> = ({dept, compact}) => {
  const color = BRAND.deptColors[dept] || BRAND.textMuted;
  return (
    <View
      style={[
        styles.badge,
        {
          backgroundColor: color + '18',
          borderColor: color + '33',
          paddingHorizontal: compact ? 8 : 12,
          paddingVertical: compact ? 2 : 4,
        },
      ]}>
      <Text style={[styles.text, {color, fontSize: compact ? 10 : 11}]}>
        {dept.toUpperCase()}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    borderRadius: 20,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  text: {
    fontWeight: '700',
    letterSpacing: 0.5,
  },
});
