import React, {useState, useEffect, useCallback, useRef} from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Modal,
  TextInput,
  ActionSheetIOS,
  Platform,
  Alert,
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
  searchFilesApi,
  ArtifactItem,
  FileScope,
  getFileDownloadUrl,
  getDownloadHeaders,
} from '../api/files';
import {
  listFoldersApi,
  createFolderApi,
  renameFolderApi,
  deleteFolderApi,
  FolderItem,
} from '../api/folders';
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

// ── Section data type ─────────────────────────────────────────────────────────

type SectionState = {
  folders: FolderItem[];
  files: ArtifactItem[];
  loading: boolean;
  error: string | null;
};

const emptySectionState = (): SectionState => ({
  folders: [], files: [], loading: true, error: null,
});

// ── Folder modal state type ───────────────────────────────────────────────────

type FolderModalState = {
  visible: boolean;
  mode: 'create' | 'rename';
  scope: FileScope;
  folder?: FolderItem;
  name: string;
};

// ── Rename file modal state type ─────────────────────────────────────────────

type RenameFileModal = {
  visible: boolean;
  file?: ArtifactItem;
  name: string;
};

// ── Main screen ───────────────────────────────────────────────────────────────

export const FilesScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const user = useAuthStore(s => s.user);
  const colors = useTheme();

  const [sections, setSections] = useState<Record<FileScope, SectionState>>({
    company: emptySectionState(),
    department: emptySectionState(),
    personal: emptySectionState(),
  });
  const [refreshing, setRefreshing] = useState(false);
  const [downloadState, setDownloadState] = useState<Record<string, number | 'done' | 'error'>>({});
  const [folderModal, setFolderModal] = useState<FolderModalState>({
    visible: false, mode: 'create', scope: 'personal', name: '',
  });
  const [uploading, setUploading] = useState<Record<FileScope, boolean>>({
    company: false, department: false, personal: false,
  });
  const [searchActive, setSearchActive] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ArtifactItem[] | null>(null);
  const [renameFileModal, setRenameFileModal] = useState<RenameFileModal>({
    visible: false, name: '',
  });
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Data loading ────────────────────────────────────────────────────────────

  const loadSection = useCallback(async (scope: FileScope) => {
    setSections(prev => ({...prev, [scope]: {...prev[scope], loading: true, error: null}}));
    try {
      const [foldersRes, filesRes] = await Promise.all([
        listFoldersApi(scope),
        listFilesApi(scope, null),
      ]);
      setSections(prev => ({
        ...prev,
        [scope]: {folders: foldersRes.folders, files: filesRes.artifacts, loading: false, error: null},
      }));
    } catch {
      setSections(prev => ({...prev, [scope]: {...prev[scope], loading: false, error: 'Failed to load'}}));
    }
  }, []);

  const loadAll = useCallback(async (isRefresh = false) => {
    if (isRefresh) { setRefreshing(true); }
    await Promise.all([loadSection('company'), loadSection('department'), loadSection('personal')]);
    setRefreshing(false);
  }, [loadSection]);

  useEffect(() => { loadAll(); }, [loadAll]);

  useEffect(() => {
    if (searchDebounceRef.current) { clearTimeout(searchDebounceRef.current); }
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    searchDebounceRef.current = setTimeout(async () => {
      try {
        const res = await searchFilesApi(searchQuery.trim());
        setSearchResults(res.results);
      } catch {
        setSearchResults([]);
      }
    }, 300);
    return () => { if (searchDebounceRef.current) { clearTimeout(searchDebounceRef.current); } };
  }, [searchQuery]);

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

  const handleUpload = useCallback(async (scope: FileScope, folderId?: string) => {
    try {
      const result = await DocumentPicker.pickSingle({type: [DocTypes.allFiles]});
      setUploading(prev => ({...prev, [scope]: true}));
      await uploadFileApi(
        result.uri,
        result.name ?? 'upload',
        result.type ?? 'application/octet-stream',
        scope,
        folderId,
      );
      await loadSection(scope);
    } catch (err: any) {
      if (!DocumentPicker.isCancel(err)) {
        Alert.alert('Upload Failed', 'Could not upload the file. Please try again.');
      }
    } finally {
      setUploading(prev => ({...prev, [scope]: false}));
    }
  }, [loadSection]);

  // ── Move file ────────────────────────────────────────────────────────────────

  const handleMoveFile = useCallback((file: ArtifactItem) => {
    const sectionFolders = sections[file.scope].folders;
    const options: {label: string; folderId: string | null}[] = [
      {label: '📁 Root (no folder)', folderId: null},
      ...sectionFolders
        .filter(f => f.id !== file.folder_id)
        .map(f => ({label: `📁 ${f.name}`, folderId: f.id})),
    ];
    Alert.alert(
      'Move to folder',
      `"${file.filename}"`,
      [
        {text: 'Cancel', style: 'cancel'},
        ...options.map(opt => ({
          text: opt.label,
          onPress: async () => {
            try {
              await moveFileApi(file.id, opt.folderId);
              await loadSection(file.scope);
            } catch {
              Alert.alert('Error', 'Failed to move file.');
            }
          },
        })),
      ],
    );
  }, [sections, loadSection]);

  // ── Folder CRUD ─────────────────────────────────────────────────────────────

  const openCreateFolder = (scope: FileScope) =>
    setFolderModal({visible: true, mode: 'create', scope, name: ''});

  const openRenameFolder = (folder: FolderItem) =>
    setFolderModal({visible: true, mode: 'rename', scope: folder.scope, folder, name: folder.name});

  const submitFolderModal = useCallback(async () => {
    const {mode, scope, folder, name} = folderModal;
    const trimmed = name.trim();
    if (!trimmed) { return; }
    setFolderModal(prev => ({...prev, visible: false}));
    try {
      if (mode === 'create') {
        await createFolderApi(trimmed, scope);
      } else if (folder) {
        await renameFolderApi(folder.id, trimmed);
      }
      await loadSection(scope);
    } catch {
      Alert.alert('Error', `Failed to ${mode} folder.`);
    }
  }, [folderModal, loadSection]);

  const handleDeleteFolder = useCallback((folder: FolderItem) => {
    Alert.alert(
      'Delete Folder',
      `Delete "${folder.name}"? Files inside will be moved to the root of this section.`,
      [
        {text: 'Cancel', style: 'cancel'},
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteFolderApi(folder.id);
              await loadSection(folder.scope);
            } catch {
              Alert.alert('Error', 'Failed to delete folder.');
            }
          },
        },
      ],
    );
  }, [loadSection]);

  const showFolderActions = useCallback((folder: FolderItem) => {
    const doRename = () => openRenameFolder(folder);
    const doDelete = () => handleDeleteFolder(folder);
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {options: ['Cancel', 'Rename', 'Delete'], destructiveButtonIndex: 2, cancelButtonIndex: 0},
        idx => {
          if (idx === 1) { doRename(); }
          if (idx === 2) { doDelete(); }
        },
      );
    } else {
      Alert.alert(folder.name, undefined, [
        {text: 'Rename', onPress: doRename},
        {text: 'Delete', style: 'destructive', onPress: doDelete},
        {text: 'Cancel', style: 'cancel'},
      ]);
    }
  }, [handleDeleteFolder]);

  const showSectionActions = useCallback((scope: FileScope) => {
    const doNewFolder = () => openCreateFolder(scope);
    const doUpload = () => handleUpload(scope);
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {options: ['Cancel', 'New Folder', 'Upload File'], cancelButtonIndex: 0},
        idx => {
          if (idx === 1) { doNewFolder(); }
          if (idx === 2) { doUpload(); }
        },
      );
    } else {
      const scopeLabel = scope.charAt(0).toUpperCase() + scope.slice(1);
      Alert.alert(`Add to ${scopeLabel}`, undefined, [
        {text: 'New Folder', onPress: doNewFolder},
        {text: 'Upload File', onPress: doUpload},
        {text: 'Cancel', style: 'cancel'},
      ]);
    }
  }, [handleUpload]);

  // ── Rename file ─────────────────────────────────────────────────────────────

  const canRename = (f: ArtifactItem): boolean => {
    if (!user) { return false; }
    return f.created_by_id === user.id;
  };

  const openRenameFile = (f: ArtifactItem) =>
    setRenameFileModal({visible: true, file: f, name: f.filename});

  const submitRenameFileModal = useCallback(async () => {
    const {file, name} = renameFileModal;
    const trimmed = name.trim();
    if (!trimmed || !file) { return; }
    setRenameFileModal(prev => ({...prev, visible: false}));
    try {
      await renameFileApi(file.id, trimmed);
      await loadSection(file.scope);
      if (searchResults !== null && searchQuery.trim()) {
        const res = await searchFilesApi(searchQuery.trim());
        setSearchResults(res.results);
      }
    } catch {
      Alert.alert('Error', 'Failed to rename file.');
    }
  }, [renameFileModal, loadSection, searchResults, searchQuery]);

  // ── Search result render ─────────────────────────────────────────────────────

  const renderSearchResult = (f: ArtifactItem) => {
    const typeKey = getTypeKey(f.filename, f.file_type);
    const ts = FILE_TYPE_STYLES[typeKey] || FILE_TYPE_STYLES.md;
    const viewerType = getViewerType(f.filename, f.file_type);
    const scopeBadgeColor = f.scope === 'company' ? colors.info : f.scope === 'department' ? colors.accent : colors.textMuted;
    const scopeLabel = f.scope === 'company' ? 'COMPANY' : f.scope === 'department' ? 'DEPT' : 'PERSONAL';
    return (
      <TouchableOpacity
        key={f.id}
        style={[styles.card, {borderTopColor: colors.border}]}
        activeOpacity={viewerType ? 0.7 : 1}
        onPress={() => viewerType && navigation.navigate('FileViewer', {file: f})}>
        <View style={[styles.typeIcon, {backgroundColor: ts.bg}]}>
          <Text style={[styles.typeLabel, {color: ts.color}]}>{ts.label}</Text>
        </View>
        <View style={{flex: 1, marginRight: 8}}>
          <View style={{flexDirection: 'row', alignItems: 'center', gap: 6}}>
            <Text style={[styles.fileName, {color: colors.text, flex: 1}]} numberOfLines={1}>{f.filename}</Text>
            <View style={[styles.scopeBadge, {backgroundColor: scopeBadgeColor + '20', borderColor: scopeBadgeColor + '40'}]}>
              <Text style={[styles.scopeBadgeText, {color: scopeBadgeColor}]}>{scopeLabel}</Text>
            </View>
          </View>
          <View style={styles.fileMeta}>
            {f.creator_name ? (
              <Text style={[styles.fileDate, {color: colors.textMuted}]}>{f.creator_name}</Text>
            ) : null}
            <Text style={[styles.fileDot, {color: colors.textDim}]}>·</Text>
            <Text style={[styles.fileDate, {color: colors.textMuted}]}>{formatDate(f.created_at)}</Text>
          </View>
        </View>
        <TouchableOpacity
          onPress={() => handleDownload(f)}
          style={styles.actionBtn}
          hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
          <Icon name="download-outline" size={18} color={colors.accent} />
        </TouchableOpacity>
      </TouchableOpacity>
    );
  };

  // ── Render helpers ──────────────────────────────────────────────────────────

  const renderFileCard = (f: ArtifactItem, canDeleteFile: boolean) => {
    const typeKey = getTypeKey(f.filename, f.file_type);
    const ts = FILE_TYPE_STYLES[typeKey] || FILE_TYPE_STYLES.md;
    const viewerType = getViewerType(f.filename, f.file_type);
    const dlState = downloadState[f.id];
    const isDownloading = typeof dlState === 'number';
    const canRenameFile = canRename(f);

    return (
      <TouchableOpacity
        key={f.id}
        style={[styles.card, {borderTopColor: colors.border}]}
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
          </View>
          {f.creator_name ? (
            <Text style={[styles.fileDate, {color: colors.textMuted}]}>{f.creator_name}</Text>
          ) : null}
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
          {canDeleteFile ? (
            <TouchableOpacity
              onPress={() =>
                Alert.alert('Delete File', `Delete "${f.filename}"?`, [
                  {text: 'Cancel', style: 'cancel'},
                  {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                      try { await deleteFileApi(f.id); await loadSection(f.scope); }
                      catch { Alert.alert('Error', 'Failed to delete file.'); }
                    },
                  },
                ])
              }
              style={styles.actionBtn}
              hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
              <Icon name="trash-outline" size={18} color={colors.danger} />
            </TouchableOpacity>
          ) : null}
          {canDeleteFile ? (
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
  };

  const renderSection = (scope: FileScope, label: string) => {
    const {folders, files, loading, error} = sections[scope];
    const write = canWrite(scope, user);
    const isEmpty = !loading && !error && folders.length === 0 && files.length === 0;

    return (
      <View
        key={scope}
        style={[styles.section, {borderColor: colors.border, backgroundColor: colors.surfaceLight}]}>
        {/* Section header */}
        <View style={styles.sectionHeader}>
          <Text style={[styles.sectionTitle, {color: colors.textMuted}]}>{label}</Text>
          {write && !loading ? (
            uploading[scope] ? (
              <ActivityIndicator size="small" color={colors.accent} />
            ) : (
              <TouchableOpacity
                onPress={() => showSectionActions(scope)}
                style={styles.addBtn}
                hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
                <Icon name="add-circle-outline" size={20} color={colors.accent} />
              </TouchableOpacity>
            )
          ) : null}
        </View>

        {loading ? (
          <ActivityIndicator size="small" color={colors.accent} style={{marginVertical: 12}} />
        ) : error ? (
          <Text style={[styles.errorText, {color: colors.danger}]}>{error}</Text>
        ) : isEmpty ? (
          <Text style={[styles.emptyText, {color: colors.textDim}]}>No files yet</Text>
        ) : (
          <>
            {folders.map(folder => (
              <TouchableOpacity
                key={folder.id}
                style={[styles.folderRow, {borderTopColor: colors.border}]}
                onPress={() => navigation.navigate('FolderContents', {folder, scope})}
                activeOpacity={0.7}>
                <Icon name="folder" size={20} color={colors.accent} style={{marginRight: 10}} />
                <Text style={[styles.folderName, {color: colors.text}]} numberOfLines={1}>
                  {folder.name}
                </Text>
                <Icon name="chevron-forward" size={14} color={colors.textDim} />
                {write ? (
                  <TouchableOpacity
                    onPress={() => showFolderActions(folder)}
                    style={{paddingLeft: 10}}
                    hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
                    <Icon name="ellipsis-horizontal" size={16} color={colors.textMuted} />
                  </TouchableOpacity>
                ) : null}
              </TouchableOpacity>
            ))}
            {files.map(f => renderFileCard(f, write))}
          </>
        )}
      </View>
    );
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  const deptLabel = user?.department
    ? `DEPARTMENT — ${user.department.toUpperCase()}`
    : 'DEPARTMENT';

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      {/* Header */}
      <View style={[styles.header]}>
        <Text style={[styles.title, {color: colors.text}]}>Files</Text>
        <View style={{flexDirection: 'row', alignItems: 'center', gap: 4}}>
          {searchActive ? (
            <TouchableOpacity
              onPress={() => { setSearchActive(false); setSearchQuery(''); setSearchResults(null); }}
              style={{padding: 8}}>
              <Icon name="close-outline" size={22} color={colors.accent} />
            </TouchableOpacity>
          ) : (
            <TouchableOpacity onPress={() => setSearchActive(true)} style={{padding: 8}}>
              <Icon name="search-outline" size={22} color={colors.accent} />
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={() => loadAll(true)} disabled={refreshing} style={{padding: 8}}>
            {refreshing
              ? <ActivityIndicator size="small" color={colors.accent} />
              : <Icon name="refresh-outline" size={22} color={colors.accent} />}
          </TouchableOpacity>
        </View>
      </View>
      {searchActive ? (
        <View style={[styles.searchBar, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
          <Icon name="search-outline" size={16} color={colors.textDim} style={{marginRight: 6}} />
          <TextInput
            style={[styles.searchInput, {color: colors.text}]}
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="Search files..."
            placeholderTextColor={colors.textDim}
            autoFocus
            returnKeyType="search"
            clearButtonMode="while-editing"
          />
        </View>
      ) : null}

      <ScrollView
        style={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => loadAll(true)}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }>
        {searchResults !== null ? (
          searchResults.length === 0 ? (
            <Text style={[styles.emptyText, {color: colors.textDim, paddingTop: 20}]}>No files found</Text>
          ) : (
            searchResults.map(f => renderSearchResult(f))
          )
        ) : (
          <>
            {renderSection('company', 'COMPANY PUBLIC')}
            {renderSection('department', deptLabel)}
            {renderSection('personal', 'PERSONAL')}
          </>
        )}
        <View style={{height: 24}} />
      </ScrollView>

      {/* Folder create / rename modal */}
      <Modal
        visible={folderModal.visible}
        transparent
        animationType="fade"
        onRequestClose={() => setFolderModal(prev => ({...prev, visible: false}))}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, {backgroundColor: colors.surface, borderColor: colors.border}]}>
            <Text style={[styles.modalTitle, {color: colors.text}]}>
              {folderModal.mode === 'create' ? 'New Folder' : 'Rename Folder'}
            </Text>
            <TextInput
              style={[styles.modalInput, {
                color: colors.text,
                borderColor: colors.border,
                backgroundColor: colors.surfaceLight,
              }]}
              value={folderModal.name}
              onChangeText={v => setFolderModal(prev => ({...prev, name: v}))}
              placeholder="Folder name"
              placeholderTextColor={colors.textDim}
              autoFocus
              onSubmitEditing={submitFolderModal}
              returnKeyType="done"
              maxLength={255}
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity
                onPress={() => setFolderModal(prev => ({...prev, visible: false}))}
                style={[styles.modalBtn, {borderColor: colors.border}]}>
                <Text style={[styles.modalBtnText, {color: colors.textMuted}]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={submitFolderModal}
                style={[styles.modalBtn, styles.modalBtnPrimary, {backgroundColor: colors.accent}]}>
                <Text style={[styles.modalBtnText, {color: '#fff'}]}>
                  {folderModal.mode === 'create' ? 'Create' : 'Rename'}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

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
  header: {
    padding: 16,
    paddingBottom: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {fontSize: 22, fontWeight: '800'},
  list: {flex: 1, paddingHorizontal: 12},
  section: {
    borderWidth: 1,
    borderRadius: 16,
    marginBottom: 12,
    overflow: 'hidden',
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  sectionTitle: {fontSize: 11, fontWeight: '800', letterSpacing: 0.8},
  addBtn: {padding: 2},
  folderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderTopWidth: 1,
  },
  folderName: {flex: 1, fontSize: 14, fontWeight: '500'},
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 12,
    paddingHorizontal: 14,
    borderTopWidth: 1,
  },
  typeIcon: {width: 40, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center'},
  typeLabel: {fontSize: 11, fontWeight: '800'},
  fileName: {fontSize: 13, fontWeight: '600'},
  fileMeta: {flexDirection: 'row', gap: 4, marginTop: 2, alignItems: 'center'},
  fileSize: {fontSize: 11},
  fileDot: {fontSize: 11},
  fileDate: {fontSize: 11},
  actionBtn: {width: 34, height: 34, alignItems: 'center', justifyContent: 'center'},
  emptyText: {fontSize: 13, paddingHorizontal: 14, paddingBottom: 14, paddingTop: 2},
  errorText: {fontSize: 12, paddingHorizontal: 14, paddingBottom: 12},
  // Modal
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
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 12,
    marginBottom: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 12,
    borderWidth: 1,
  },
  searchInput: {flex: 1, fontSize: 15, paddingVertical: 0},
  scopeBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    borderWidth: 1,
  },
  scopeBadgeText: {fontSize: 9, fontWeight: '800', letterSpacing: 0.5},
});
