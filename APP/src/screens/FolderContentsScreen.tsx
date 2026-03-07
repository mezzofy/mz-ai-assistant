import React, {useState, useEffect, useCallback} from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Modal,
  TextInput,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import DocumentPicker, {types as DocTypes} from 'react-native-document-picker';
import RNFS from 'react-native-fs';
import Share from 'react-native-share';
import {FILE_TYPE_STYLES} from '../utils/theme';
import {useTheme} from '../hooks/useTheme';
import {useAuthStore} from '../stores/authStore';
import {canWrite} from '../utils/fileRights';
import {
  listFilesApi,
  uploadFileApi,
  deleteFileApi,
  moveFileApi,
  renameFileApi,
  ArtifactItem,
  FileScope,
  getFileDownloadUrl,
  getDownloadHeaders,
} from '../api/files';
import {FolderItem} from '../api/folders';
import {getViewerType} from '../utils/fileViewer';

// ── Helpers ───────────────────────────────────────────────────────────────────

const formatDate = (iso: string): string => {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) {
    return `Today, ${d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`;
  }
  if (d.toDateString() === yesterday.toDateString()) { return 'Yesterday'; }
  return d.toLocaleDateString('en-US', {month: 'short', day: 'numeric'});
};

const getTypeKey = (filename: string, fileType: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  if (ext && FILE_TYPE_STYLES[ext]) { return ext; }
  const t = fileType.split('/').pop()?.toLowerCase() ?? fileType.toLowerCase();
  return FILE_TYPE_STYLES[t] ? t : 'md';
};

const getMimeType = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    pdf: 'application/pdf', csv: 'text/csv', txt: 'text/plain',
    png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', mp4: 'video/mp4',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  };
  return map[ext] ?? 'application/octet-stream';
};

// ── Rename file modal type ────────────────────────────────────────────────────

type RenameFileModal = {
  visible: boolean;
  file?: ArtifactItem;
  name: string;
};

// ── Screen ────────────────────────────────────────────────────────────────────

type Props = {
  navigation: any;
  route: {params: {folder: FolderItem; scope: FileScope}};
};

export const FolderContentsScreen: React.FC<Props> = ({navigation, route}) => {
  const {folder, scope} = route.params;
  const user = useAuthStore(s => s.user);
  const colors = useTheme();
  const write = canWrite(scope, user);

  const [files, setFiles] = useState<ArtifactItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadState, setDownloadState] = useState<Record<string, number | 'done' | 'error'>>({});
  const [uploading, setUploading] = useState(false);
  const [renameFileModal, setRenameFileModal] = useState<RenameFileModal>({
    visible: false, name: '',
  });

  const canRename = (f: ArtifactItem): boolean => {
    if (!user) { return false; }
    return f.created_by_id === user.id;
  };

  const openRenameFile = (f: ArtifactItem) =>
    setRenameFileModal({visible: true, file: f, name: f.filename});

  const loadFiles = useCallback(async (isRefresh = false) => {
    if (isRefresh) { setRefreshing(true); } else { setLoading(true); }
    setError(null);
    try {
      const res = await listFilesApi(scope, folder.id);
      setFiles(res.artifacts);
    } catch (err) {
      console.error('[FolderContentsScreen] loadFiles failed:', err);
      setError('Failed to load files');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [scope, folder.id]);

  const submitRenameFileModal = useCallback(async () => {
    const {file, name} = renameFileModal;
    const trimmed = name.trim();
    if (!trimmed || !file) { return; }
    setRenameFileModal(prev => ({...prev, visible: false}));
    try {
      await renameFileApi(file.id, trimmed);
      await loadFiles();
    } catch {
      Alert.alert('Error', 'Failed to rename file.');
    }
  }, [renameFileModal, loadFiles]);

  useEffect(() => { loadFiles(); }, [loadFiles]);

  // ── Download ────────────────────────────────────────────────────────────────

  const handleDownload = useCallback(async (file: ArtifactItem) => {
    if (typeof downloadState[file.id] === 'number') { return; }
    setDownloadState(prev => ({...prev, [file.id]: 0}));
    try {
      const url = getFileDownloadUrl(file.id);
      const headers = await getDownloadHeaders();
      const dest = `${RNFS.CachesDirectoryPath}/${file.filename}`;
      const dl = RNFS.downloadFile({
        fromUrl: url, toFile: dest, headers, progressDivider: 5,
        progress: r => {
          const pct = Math.round((r.bytesWritten / r.contentLength) * 100);
          setDownloadState(prev => ({...prev, [file.id]: pct}));
        },
      });
      const result = await dl.promise;
      if (result.statusCode === 200) {
        setDownloadState(prev => ({...prev, [file.id]: 'done'}));
        await Share.open({
          url: `file://${dest}`,
          type: getMimeType(file.filename),
          filename: file.filename,
          failOnCancel: false,
        });
        setDownloadState(prev => { const n = {...prev}; delete n[file.id]; return n; });
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
        setDownloadState(prev => { const n = {...prev}; delete n[file.id]; return n; });
      } else {
        setDownloadState(prev => ({...prev, [file.id]: 'error'}));
      }
    }
  }, [downloadState]);

  // ── Upload ──────────────────────────────────────────────────────────────────

  const handleUpload = useCallback(async () => {
    try {
      const result = await DocumentPicker.pickSingle({type: [DocTypes.allFiles]});
      setUploading(true);
      await uploadFileApi(
        result.uri,
        result.name ?? 'upload',
        result.type ?? 'application/octet-stream',
        scope,
        folder.id,
      );
      await loadFiles();
    } catch (err: any) {
      if (!DocumentPicker.isCancel(err)) {
        Alert.alert('Upload Failed', 'Could not upload the file. Please try again.');
      }
    } finally {
      setUploading(false);
    }
  }, [scope, folder.id, loadFiles]);

  // ── Delete file ─────────────────────────────────────────────────────────────

  const handleDeleteFile = useCallback((file: ArtifactItem) => {
    Alert.alert('Delete File', `Delete "${file.filename}"?`, [
      {text: 'Cancel', style: 'cancel'},
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try { await deleteFileApi(file.id); await loadFiles(); }
          catch { Alert.alert('Error', 'Failed to delete file.'); }
        },
      },
    ]);
  }, [loadFiles]);

  // ── Move file ───────────────────────────────────────────────────────────────

  const handleMoveFile = useCallback((file: ArtifactItem) => {
    Alert.alert(
      'Move file',
      `Move "${file.filename}" to root (remove from this folder)?`,
      [
        {text: 'Cancel', style: 'cancel'},
        {
          text: 'Move to Root',
          onPress: async () => {
            try {
              await moveFileApi(file.id, null);
              await loadFiles();
            } catch {
              Alert.alert('Error', 'Failed to move file.');
            }
          },
        },
      ],
    );
  }, [loadFiles]);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      {/* Header */}
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          style={styles.backBtn}
          hitSlop={{top: 10, bottom: 10, left: 10, right: 10}}>
          <Icon name="chevron-back" size={22} color={colors.accent} />
        </TouchableOpacity>
        <Text style={[styles.folderTitle, {color: colors.text}]} numberOfLines={1}>{folder.name}</Text>
        {write ? (
          uploading ? (
            <ActivityIndicator size="small" color={colors.accent} style={{marginRight: 4}} />
          ) : (
            <TouchableOpacity onPress={handleUpload} style={styles.uploadBtn} hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
              <Icon name="cloud-upload-outline" size={22} color={colors.accent} />
            </TouchableOpacity>
          )
        ) : <View style={{width: 36}} />}
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : error ? (
        <View style={styles.center}>
          <View style={[styles.errorWrap, {backgroundColor: colors.danger + '14', borderColor: colors.danger + '30'}]}>
            <Icon name="alert-circle-outline" size={14} color={colors.danger} />
            <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
          </View>
          <TouchableOpacity
            onPress={() => loadFiles()}
            style={[styles.retryBtn, {borderColor: colors.accent}]}>
            <Text style={[styles.retryText, {color: colors.accent}]}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
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
          {files.length === 0 ? (
            <View style={styles.emptyWrap}>
              <Icon name="document-outline" size={40} color={colors.textDim} />
              <Text style={[styles.emptyText, {color: colors.textDim}]}>No files in this folder</Text>
            </View>
          ) : (
            files.map(f => {
              const typeKey = getTypeKey(f.filename, f.file_type);
              const ts = FILE_TYPE_STYLES[typeKey] || FILE_TYPE_STYLES.md;
              const viewerType = getViewerType(f.filename, f.file_type);
              const dlState = downloadState[f.id];
              const isDownloading = typeof dlState === 'number';
              const canRenameFile = canRename(f);

              return (
                <TouchableOpacity
                  key={f.id}
                  style={[styles.card, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}
                  activeOpacity={viewerType ? 0.7 : 1}
                  onPress={() => viewerType && navigation.navigate('FileViewer', {file: f})}>
                  <View style={[styles.typeIcon, {backgroundColor: ts.bg}]}>
                    <Text style={[styles.typeLabel, {color: ts.color}]}>{ts.label}</Text>
                  </View>
                  <View style={{flex: 1, marginRight: 8}}>
                    <Text style={[styles.fileName, {color: colors.text}]} numberOfLines={1}>{f.filename}</Text>
                    <View style={styles.fileMeta}>
                      {f.file_size ? (
                        <>
                          <Text style={[styles.fileSize, {color: colors.textMuted}]}>{f.file_size}</Text>
                          <Text style={[styles.fileDot, {color: colors.textDim}]}>·</Text>
                        </>
                      ) : null}
                      <Text style={[styles.fileDate, {color: colors.textMuted}]}>{formatDate(f.created_at)}</Text>
                      {f.creator_name ? (
                        <>
                          <Text style={[styles.fileDot, {color: colors.textDim}]}>·</Text>
                          <Text style={[styles.fileDate, {color: colors.textMuted}]}>{f.creator_name}</Text>
                        </>
                      ) : null}
                    </View>
                  </View>
                  <View style={{flexDirection: 'row', alignItems: 'center', gap: 4}}>
                    {viewerType ? (
                      <TouchableOpacity
                        onPress={() => navigation.navigate('FileViewer', {file: f})}
                        style={styles.actionBtn}
                        hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
                        <Icon name="eye-outline" size={18} color={colors.info} />
                      </TouchableOpacity>
                    ) : null}
                    {write ? (
                      <TouchableOpacity
                        onPress={() => handleDeleteFile(f)}
                        style={styles.actionBtn}
                        hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
                        <Icon name="trash-outline" size={18} color={colors.danger} />
                      </TouchableOpacity>
                    ) : null}
                    {write ? (
                      <TouchableOpacity
                        onPress={() => handleMoveFile(f)}
                        style={styles.actionBtn}
                        hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
                        <Icon name="folder-open-outline" size={18} color={colors.textMuted} />
                      </TouchableOpacity>
                    ) : null}
                    {canRenameFile ? (
                      <TouchableOpacity
                        onPress={() => openRenameFile(f)}
                        style={styles.actionBtn}
                        hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
                        <Icon name="pencil-outline" size={18} color={colors.textMuted} />
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
                            <Text style={{fontSize: 9, color: colors.accent, fontWeight: '700'}}>{dlState}%</Text>
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
          <View style={{height: 24}} />
        </ScrollView>
      )}

      {/* File rename modal */}
      <Modal
        visible={renameFileModal.visible}
        transparent
        animationType="fade"
        onRequestClose={() => setRenameFileModal(prev => ({...prev, visible: false}))}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, {backgroundColor: colors.surface, borderColor: colors.border}]}>
            <Text style={[styles.modalTitle, {color: colors.text}]}>Rename File</Text>
            <TextInput
              style={[styles.modalInput, {
                color: colors.text,
                borderColor: colors.border,
                backgroundColor: colors.surfaceLight,
              }]}
              value={renameFileModal.name}
              onChangeText={v => setRenameFileModal(prev => ({...prev, name: v}))}
              placeholder="File name"
              placeholderTextColor={colors.textDim}
              autoFocus
              onSubmitEditing={submitRenameFileModal}
              returnKeyType="done"
              maxLength={255}
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity
                onPress={() => setRenameFileModal(prev => ({...prev, visible: false}))}
                style={[styles.modalBtn, {borderColor: colors.border}]}>
                <Text style={[styles.modalBtnText, {color: colors.textMuted}]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={submitRenameFileModal}
                style={[styles.modalBtn, styles.modalBtnPrimary, {backgroundColor: colors.accent}]}>
                <Text style={[styles.modalBtnText, {color: '#fff'}]}>Rename</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {flex: 1},
  center: {flex: 1, justifyContent: 'center', alignItems: 'center'},
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  backBtn: {padding: 4, marginRight: 8},
  folderTitle: {flex: 1, fontSize: 18, fontWeight: '700'},
  uploadBtn: {padding: 4},
  list: {flex: 1, paddingHorizontal: 16},
  emptyWrap: {alignItems: 'center', paddingTop: 60, gap: 12},
  emptyText: {fontSize: 14},
  errorWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    margin: 16,
    padding: 10,
    borderRadius: 10,
    borderWidth: 1,
  },
  errorText: {flex: 1, fontSize: 12},
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    paddingHorizontal: 16,
    borderRadius: 14,
    marginBottom: 8,
    borderWidth: 1,
    marginTop: 8,
  },
  typeIcon: {width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center'},
  typeLabel: {fontSize: 11, fontWeight: '800'},
  fileName: {fontSize: 13, fontWeight: '600'},
  fileMeta: {flexDirection: 'row', gap: 4, marginTop: 3, alignItems: 'center'},
  fileSize: {fontSize: 11},
  fileDot: {fontSize: 11},
  fileDate: {fontSize: 11},
  actionBtn: {width: 36, height: 36, alignItems: 'center', justifyContent: 'center'},
  retryBtn: {marginTop: 12, paddingHorizontal: 20, paddingVertical: 8, borderRadius: 20, borderWidth: 1},
  retryText: {fontSize: 13, fontWeight: '600'},
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalBox: {width: 300, borderRadius: 16, padding: 20, borderWidth: 1},
  modalTitle: {fontSize: 16, fontWeight: '700', marginBottom: 14},
  modalInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
    marginBottom: 16,
  },
  modalButtons: {flexDirection: 'row', gap: 10, justifyContent: 'flex-end'},
  modalBtn: {
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 10,
    borderWidth: 1,
  },
  modalBtnPrimary: {borderWidth: 0},
  modalBtnText: {fontSize: 14, fontWeight: '600'},
});
