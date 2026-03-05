import React, {useState, useEffect, useCallback} from 'react';
import {
  View,
  Text,
  ScrollView,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
  PermissionsAndroid,
  Dimensions,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import RNFS from 'react-native-fs';
import Video from 'react-native-video';
import Markdown from 'react-native-markdown-display';
import {useTheme} from '../hooks/useTheme';
import {ArtifactItem, getFileDownloadUrl} from '../api/files';
import {getViewerType} from '../utils/fileViewer';

const markdownStyles = (colors: ReturnType<typeof useTheme>) => ({
  body:        {color: colors.text, fontSize: 14, lineHeight: 22},
  heading1:    {color: colors.text, fontSize: 22, fontWeight: '800' as const, marginBottom: 8},
  heading2:    {color: colors.text, fontSize: 18, fontWeight: '700' as const, marginBottom: 6},
  heading3:    {color: colors.text, fontSize: 16, fontWeight: '600' as const, marginBottom: 4},
  code_block:  {
    backgroundColor: colors.surfaceLight,
    borderRadius: 8,
    padding: 12,
    fontFamily: 'monospace',
    color: colors.info,
  },
  code_inline: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 4,
    color: colors.info,
    fontFamily: 'monospace',
  },
  blockquote:  {borderLeftColor: colors.accent, borderLeftWidth: 3, paddingLeft: 12, marginLeft: 0},
  link:        {color: colors.accent},
  hr:          {backgroundColor: colors.border, height: 1},
});

export const FileViewerScreen: React.FC<{navigation: any; route: any}> = ({navigation, route}) => {
  const {file} = route.params as {file: ArtifactItem};
  const colors = useTheme();
  const viewerType = getViewerType(file.filename, file.file_type);

  const [fileUri,        setFileUri]        = useState<string | null>(null);
  const [content,        setContent]        = useState<string | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [contentError,   setContentError]   = useState<string | null>(null);
  const [downloadState,  setDownloadState]  = useState<number | 'done' | 'error' | null>(null);

  // Resolve download URL; for text/markdown also fetch the text content
  useEffect(() => {
    getFileDownloadUrl(file.id)
      .then(url => {
        setFileUri(url);
        if (viewerType === 'text' || viewerType === 'markdown') {
          setLoadingContent(true);
          fetch(url)
            .then(r => {
              if (!r.ok) { throw new Error(`HTTP ${r.status}`); }
              return r.text();
            })
            .then(text => setContent(text))
            .catch(e => setContentError(e.message ?? 'Failed to load file'))
            .finally(() => setLoadingContent(false));
        }
      })
      .catch(() => setContentError('Failed to resolve file URL'));
  }, [file.id, viewerType]);

  const handleDownload = useCallback(async () => {
    if (typeof downloadState === 'number' || !fileUri) { return; }

    if (Platform.OS === 'android' && (Platform.Version as number) < 29) {
      const granted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.WRITE_EXTERNAL_STORAGE,
        {
          title: 'Storage Permission',
          message: 'Mezzofy AI needs storage access to save files.',
          buttonPositive: 'Allow',
        },
      );
      if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
        setDownloadState('error');
        return;
      }
    }

    setDownloadState(0);
    try {
      const dest =
        Platform.OS === 'android'
          ? `${RNFS.DownloadDirectoryPath}/${file.filename}`
          : `${RNFS.DocumentDirectoryPath}/${file.filename}`;

      const dl = RNFS.downloadFile({
        fromUrl: fileUri,
        toFile: dest,
        progressDivider: 5,
        progress: r =>
          setDownloadState(Math.round((r.bytesWritten / r.contentLength) * 100)),
      });

      const result = await dl.promise;
      if (result.statusCode === 200) {
        setDownloadState('done');
        setTimeout(() => setDownloadState(null), 2500);
      } else {
        setDownloadState('error');
      }
    } catch {
      setDownloadState('error');
    }
  }, [downloadState, fileUri, file.filename]);

  const isDownloading = typeof downloadState === 'number';

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      {/* Header */}
      <View style={[styles.header, {backgroundColor: colors.primary, borderBottomColor: colors.border}]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Icon name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, {color: colors.text}]} numberOfLines={1}>
          {file.filename}
        </Text>
        <TouchableOpacity
          onPress={handleDownload}
          disabled={isDownloading}
          style={styles.headerAction}>
          {isDownloading ? (
            <ActivityIndicator size="small" color={colors.accent} />
          ) : downloadState === 'done' ? (
            <Icon name="checkmark-circle" size={22} color={colors.success} />
          ) : downloadState === 'error' ? (
            <Icon name="alert-circle-outline" size={22} color={colors.danger} />
          ) : (
            <Icon name="download-outline" size={22} color={colors.accent} />
          )}
        </TouchableOpacity>
      </View>

      {/* Loading */}
      {(loadingContent || (!fileUri && !contentError)) && (
        <View style={[styles.center, {flex: 1, backgroundColor: colors.primary}]}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      )}

      {/* Error */}
      {contentError && (
        <View style={[styles.center, {flex: 1, backgroundColor: colors.primary}]}>
          <Icon name="alert-circle-outline" size={40} color={colors.danger} />
          <Text
            style={{
              color: colors.danger,
              marginTop: 8,
              textAlign: 'center',
              paddingHorizontal: 32,
            }}>
            {contentError}
          </Text>
        </View>
      )}

      {/* Image */}
      {viewerType === 'image' && fileUri && !contentError && (
        <ScrollView
          style={{flex: 1, backgroundColor: '#000'}}
          maximumZoomScale={5}
          minimumZoomScale={1}
          centerContent>
          <Image
            source={{uri: fileUri}}
            style={styles.fullImage}
            resizeMode="contain"
          />
        </ScrollView>
      )}

      {/* Video */}
      {viewerType === 'video' && fileUri && !contentError && (
        <View style={{flex: 1, backgroundColor: '#000', justifyContent: 'center'}}>
          <Video
            source={{uri: fileUri}}
            style={styles.videoPlayer}
            controls={true}
            resizeMode="contain"
            onError={() => setContentError('Failed to play video')}
          />
        </View>
      )}

      {/* Markdown */}
      {viewerType === 'markdown' && !loadingContent && content !== null && !contentError && (
        <ScrollView
          style={{flex: 1, backgroundColor: colors.primary}}
          contentContainerStyle={{padding: 16, paddingBottom: 40}}>
          <Markdown style={markdownStyles(colors)}>{content}</Markdown>
        </ScrollView>
      )}

      {/* Text / Code */}
      {viewerType === 'text' && !loadingContent && content !== null && !contentError && (
        <ScrollView style={{flex: 1, backgroundColor: colors.primary}}>
          <ScrollView horizontal>
            <Text style={[styles.monoText, {color: colors.text}]}>{content}</Text>
          </ScrollView>
        </ScrollView>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container:    {flex: 1},
  header:       {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn:      {padding: 8},
  headerTitle:  {flex: 1, fontSize: 16, fontWeight: '700', marginLeft: 4, marginRight: 4},
  headerAction: {padding: 8, width: 40, alignItems: 'center'},
  center:       {alignItems: 'center', justifyContent: 'center'},
  fullImage:    {width: Dimensions.get('window').width, aspectRatio: 1},
  videoPlayer:  {width: '100%', aspectRatio: 16 / 9},
  monoText:     {fontFamily: 'monospace', fontSize: 13, lineHeight: 20, padding: 16},
});
