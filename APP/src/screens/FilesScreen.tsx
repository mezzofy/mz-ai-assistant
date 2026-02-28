import React, {useState, useEffect} from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {BRAND, FILE_TYPE_STYLES} from '../utils/theme';
import {listFilesApi, ArtifactItem} from '../api/files';

const formatDate = (iso: string): string => {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) {
    return `Today, ${d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`;
  }
  if (d.toDateString() === yesterday.toDateString()) {
    return 'Yesterday';
  }
  return d.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
};

// Derives a FILE_TYPE_STYLES key from the filename extension or file_type string.
// Falls back to 'md' (white label) if unknown.
const getTypeKey = (filename: string, fileType: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  if (ext && FILE_TYPE_STYLES[ext]) {
    return ext;
  }
  const t = fileType.split('/').pop()?.toLowerCase() ?? fileType.toLowerCase();
  return FILE_TYPE_STYLES[t] ? t : 'md';
};

export const FilesScreen: React.FC = () => {
  const [files, setFiles] = useState<ArtifactItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listFilesApi()
      .then(res => setFiles(res.artifacts))
      .catch(() => setError('Failed to load files'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color={BRAND.accent} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Generated Files</Text>
        <Text style={styles.count}>{files.length} files</Text>
      </View>

      {error ? (
        <View style={styles.errorWrap}>
          <Icon name="alert-circle-outline" size={14} color={BRAND.danger} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <ScrollView style={styles.list}>
        {files.length === 0 && !error ? (
          <View style={styles.emptyWrap}>
            <Icon name="document-outline" size={40} color={BRAND.textDim} />
            <Text style={styles.emptyText}>No files yet</Text>
          </View>
        ) : (
          files.map(f => {
            const typeKey = getTypeKey(f.filename, f.file_type);
            const ts = FILE_TYPE_STYLES[typeKey] || FILE_TYPE_STYLES.md;
            return (
              <TouchableOpacity key={f.id} style={styles.card} activeOpacity={0.7}>
                <View style={[styles.typeIcon, {backgroundColor: ts.bg}]}>
                  <Text style={[styles.typeLabel, {color: ts.color}]}>{ts.label}</Text>
                </View>
                <View style={{flex: 1, marginRight: 8}}>
                  <Text style={styles.fileName} numberOfLines={1}>
                    {f.filename}
                  </Text>
                  <View style={styles.fileMeta}>
                    {f.file_size ? (
                      <>
                        <Text style={styles.fileSize}>{f.file_size}</Text>
                        <Text style={styles.fileDot}>·</Text>
                      </>
                    ) : null}
                    <Text style={styles.fileDate}>{formatDate(f.created_at)}</Text>
                  </View>
                </View>
                <Icon
                  name="download-outline"
                  size={18}
                  color={BRAND.accent}
                  style={{marginLeft: 8}}
                />
              </TouchableOpacity>
            );
          })
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: BRAND.primary},
  center: {justifyContent: 'center', alignItems: 'center'},
  header: {padding: 16, paddingBottom: 8},
  title: {color: BRAND.text, fontSize: 20, fontWeight: '800'},
  count: {color: BRAND.textMuted, fontSize: 12, marginTop: 2},
  errorWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginHorizontal: 16,
    marginBottom: 8,
    padding: 10,
    borderRadius: 10,
    backgroundColor: BRAND.danger + '14',
    borderWidth: 1,
    borderColor: BRAND.danger + '30',
  },
  errorText: {flex: 1, color: BRAND.danger, fontSize: 12},
  emptyWrap: {alignItems: 'center', paddingTop: 60, gap: 12},
  emptyText: {color: BRAND.textDim, fontSize: 14},
  list: {flex: 1, paddingHorizontal: 16},
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    paddingHorizontal: 16,
    borderRadius: 14,
    marginBottom: 8,
    backgroundColor: BRAND.surfaceLight,
    borderWidth: 1,
    borderColor: BRAND.border,
  },
  typeIcon: {width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center'},
  typeLabel: {fontSize: 11, fontWeight: '800'},
  fileName: {color: BRAND.text, fontSize: 13, fontWeight: '600'},
  fileMeta: {flexDirection: 'row', gap: 4, marginTop: 3, alignItems: 'center'},
  fileSize: {fontSize: 11, color: BRAND.textMuted},
  fileDot: {fontSize: 11, color: BRAND.textDim},
  fileDate: {fontSize: 11, color: BRAND.textMuted},
});
