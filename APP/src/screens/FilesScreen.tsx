import React, {useState, useEffect, useCallback} from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import RNFS from 'react-native-fs';
import Share from 'react-native-share';
import {FILE_TYPE_STYLES} from '../utils/theme';
import {useTheme} from '../hooks/useTheme';
import {listFilesApi, ArtifactItem, getFileDownloadUrl, getDownloadHeaders} from '../api/files';
import {getViewerType} from '../utils/fileViewer';

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

const getMimeType = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    pdf: 'application/pdf',
    csv: 'text/csv',
    txt: 'text/plain',
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    mp4: 'video/mp4',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  };
  return map[ext] ?? 'application/octet-stream';
};

export const FilesScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const [files, setFiles] = useState<ArtifactItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadState, setDownloadState] = useState<
    Record<string, number | 'done' | 'error'>
  >({});
  const colors = useTheme();

  const loadFiles = useCallback(async (isRefresh = false) => {
    if (isRefresh) { setRefreshing(true); } else { setLoading(true); }
    setError(null);
    try {
      const res = await listFilesApi();
      setFiles(res.artifacts);
    } catch {
      setError('Failed to load files');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadFiles(); }, [loadFiles]);

  const handleDownload = useCallback(async (file: ArtifactItem) => {
    if (typeof downloadState[file.id] === 'number') { return; }

    setDownloadState(prev => ({...prev, [file.id]: 0}));
    try {
      const url = getFileDownloadUrl(file.id);
      const headers = await getDownloadHeaders();
      // Download to cache (temp) — share sheet lets user decide final destination
      const dest = `${RNFS.CachesDirectoryPath}/${file.filename}`;

      const dl = RNFS.downloadFile({
        fromUrl: url,
        toFile: dest,
        headers,
        progressDivider: 5,
        progress: r => {
          const pct = Math.round((r.bytesWritten / r.contentLength) * 100);
          setDownloadState(prev => ({...prev, [file.id]: pct}));
        },
      });

      const result = await dl.promise;
      if (result.statusCode === 200) {
        setDownloadState(prev => ({...prev, [file.id]: 'done'}));
        // Open native share sheet — user chooses where to save or share
        await Share.open({
          url: `file://${dest}`,
          type: getMimeType(file.filename),
          filename: file.filename,
          failOnCancel: false,
        });
        // Reset after share sheet dismissed
        setDownloadState(prev => {
          const next = {...prev};
          delete next[file.id];
          return next;
        });
      } else {
        setDownloadState(prev => ({...prev, [file.id]: 'error'}));
      }
    } catch (err: any) {
      const msg: string = err?.message ?? '';
      const isCancel =
        msg === 'User did not share' ||
        msg.toLowerCase().includes('cancel') ||
        err?.error?.toLowerCase?.()?.includes('cancel');
      if (isCancel) {
        // User cancelled share sheet — reset cleanly
        setDownloadState(prev => {
          const next = {...prev};
          delete next[file.id];
          return next;
        });
      } else {
        setDownloadState(prev => ({...prev, [file.id]: 'error'}));
      }
    }
  }, [downloadState]);

  if (loading) {
    return (
      <View style={[styles.container, styles.center, {backgroundColor: colors.primary}]}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      <View style={[styles.header, {flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start'}]}>
        <View>
          <Text style={[styles.title, {color: colors.text}]}>Generated Files</Text>
          <Text style={[styles.count, {color: colors.textMuted}]}>{files.length} files</Text>
        </View>
        <TouchableOpacity
          onPress={() => loadFiles(true)}
          disabled={refreshing || loading}
          style={{padding: 8}}>
          {refreshing
            ? <ActivityIndicator size="small" color={colors.accent} />
            : <Icon name="refresh-outline" size={22} color={colors.accent} />}
        </TouchableOpacity>
      </View>

      {error ? (
        <View style={[styles.errorWrap, {backgroundColor: colors.danger + '14', borderColor: colors.danger + '30'}]}>
          <Icon name="alert-circle-outline" size={14} color={colors.danger} />
          <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
        </View>
      ) : null}

      <ScrollView
        style={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => loadFiles(true)}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }>
        {files.length === 0 && !error ? (
          <View style={styles.emptyWrap}>
            <Icon name="document-outline" size={40} color={colors.textDim} />
            <Text style={[styles.emptyText, {color: colors.textDim}]}>No files yet</Text>
          </View>
        ) : (
          files.map(f => {
            const typeKey    = getTypeKey(f.filename, f.file_type);
            const ts         = FILE_TYPE_STYLES[typeKey] || FILE_TYPE_STYLES.md;
            const viewerType = getViewerType(f.filename, f.file_type);
            const dlState    = downloadState[f.id];
            const isDownloading = typeof dlState === 'number';

            return (
              <TouchableOpacity
                key={f.id}
                style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}
                activeOpacity={viewerType ? 0.7 : 1}
                onPress={() => viewerType && navigation.navigate('FileViewer', {file: f})}>

                {/* Type badge */}
                <View style={[styles.typeIcon, {backgroundColor: ts.bg}]}>
                  <Text style={[styles.typeLabel, {color: ts.color}]}>{ts.label}</Text>
                </View>

                {/* Filename + meta */}
                <View style={{flex: 1, marginRight: 8}}>
                  <Text style={[styles.fileName, {color: colors.text}]} numberOfLines={1}>
                    {f.filename}
                  </Text>
                  <View style={styles.fileMeta}>
                    {f.file_size ? (
                      <>
                        <Text style={[styles.fileSize, {color: colors.textMuted}]}>{f.file_size}</Text>
                        <Text style={[styles.fileDot, {color: colors.textDim}]}>·</Text>
                      </>
                    ) : null}
                    <Text style={[styles.fileDate, {color: colors.textMuted}]}>{formatDate(f.created_at)}</Text>
                  </View>
                </View>

                {/* Action buttons */}
                <View style={{flexDirection: 'row', alignItems: 'center', gap: 4}}>
                  {viewerType ? (
                    <TouchableOpacity
                      onPress={() => navigation.navigate('FileViewer', {file: f})}
                      style={styles.actionBtn}
                      hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
                      <Icon name="eye-outline" size={18} color={colors.info} />
                    </TouchableOpacity>
                  ) : null}

                  <TouchableOpacity
                    onPress={() => handleDownload(f)}
                    disabled={isDownloading}
                    style={styles.actionBtn}
                    hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
                    {isDownloading ? (
                      <View style={{alignItems: 'center'}}>
                        <ActivityIndicator size="small" color={colors.accent} />
                        {(dlState as number) > 0 ? (
                          <Text style={{fontSize: 9, color: colors.accent, fontWeight: '700'}}>
                            {dlState}%
                          </Text>
                        ) : null}
                      </View>
                    ) : dlState === 'done' ? (
                      <Icon name="checkmark-circle" size={18} color={colors.success} />
                    ) : dlState === 'error' ? (
                      <Icon name="alert-circle-outline" size={18} color={colors.danger} />
                    ) : (
                      <Icon name="download-outline" size={18} color={colors.accent} />
                    )}
                  </TouchableOpacity>
                </View>
              </TouchableOpacity>
            );
          })
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  center: {justifyContent: 'center', alignItems: 'center'},
  header: {padding: 16, paddingBottom: 8},
  title: {fontSize: 20, fontWeight: '800'},
  count: {fontSize: 12, marginTop: 2},
  errorWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginHorizontal: 16,
    marginBottom: 8,
    padding: 10,
    borderRadius: 10,
    borderWidth: 1,
  },
  errorText: {flex: 1, fontSize: 12},
  emptyWrap: {alignItems: 'center', paddingTop: 60, gap: 12},
  emptyText: {fontSize: 14},
  list: {flex: 1, paddingHorizontal: 16},
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    paddingHorizontal: 16,
    borderRadius: 14,
    marginBottom: 8,
    borderWidth: 1,
  },
  typeIcon: {width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center'},
  typeLabel: {fontSize: 11, fontWeight: '800'},
  fileName: {fontSize: 13, fontWeight: '600'},
  fileMeta: {flexDirection: 'row', gap: 4, marginTop: 3, alignItems: 'center'},
  fileSize: {fontSize: 11},
  fileDot: {fontSize: 11},
  fileDate: {fontSize: 11},
  actionBtn: {width: 36, height: 36, alignItems: 'center', justifyContent: 'center'},
});
