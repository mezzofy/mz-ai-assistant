import React, {useState, useRef, useEffect} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  StyleSheet, KeyboardAvoidingView, Platform, Modal, ActivityIndicator,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {launchImageLibrary} from 'react-native-image-picker';
import DocumentPicker, {types as DocTypes, isCancel as isDocPickerCancel} from 'react-native-document-picker';
import Voice, {SpeechResultsEvent} from '@react-native-voice/voice';
import {INPUT_MODES, FILE_TYPE_STYLES} from '../utils/theme';
import {useTheme} from '../hooks/useTheme';
import {useAuthStore} from '../stores/authStore';
import {useSettingsStore} from '../stores/settingsStore';
import {useChatStore, Message, MediaInfo, SelectedArtifact} from '../stores/chatStore';
import {listFilesApi, ArtifactItem} from '../api/files';
import {DeptBadge} from '../components/shared/DeptBadge';

const SPEECH_LOCALE: Record<string, string> = {
  English: 'en-US',
  Chinese: 'zh-CN',
};

const formatBytes = (bytes?: number): string => {
  if (!bytes) {return '—';}
  if (bytes < 1024) {return `${bytes} B`;}
  if (bytes < 1024 * 1024) {return `${(bytes / 1024).toFixed(1)} KB`;}
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

function normalizeApiError(raw: string): string {
  const lower = raw.toLowerCase();
  if (lower.includes('both') && lower.includes('model')) {
    return 'AI is temporarily busy. Please try again.';
  }
  if (lower.includes('network') || lower.includes('fetch')) {
    return 'No connection. Check your network and retry.';
  }
  if (lower.includes('timeout')) {
    return 'Request timed out. Please try again.';
  }
  return raw;
}

export const ChatScreen: React.FC<{navigation: any}> = ({navigation}) => {
  // ── All hooks MUST be called unconditionally (Rules of Hooks) ──────────────
  const user = useAuthStore(s => s.user);
  const speechLanguage = useSettingsStore(s => s.speechLanguage);
  const colors = useTheme();
  const {
    messages, isTyping, inputMode, showModes, recording, recordTime,
    mediaPreview, selectedArtifact, error: chatError, sessionId, sessionTitles,
    activeTask, pollActiveTask, clearActiveTask,
    setInputMode, setShowModes, setRecording, setRecordTime, setMediaPreview,
    setSelectedArtifact, sendToServer, sendArtifactToServer, clearError,
    resetChat, setSessionId, setSessionTitle,
  } = useChatStore();
  const [input, setInput] = useState('');
  const [mediaUri, setMediaUri] = useState<string | null>(null);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [editingTitle, setEditingTitle] = useState(false);
  const [showMyFilesModal, setShowMyFilesModal] = useState(false);
  const [myFilesList, setMyFilesList] = useState<ArtifactItem[]>([]);
  const [myFilesLoading, setMyFilesLoading] = useState(false);
  const [myFilesError, setMyFilesError] = useState<string | null>(null);
  const scrollRef = useRef<ScrollView>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const titleInputRef = useRef<TextInput>(null);

  const currentTitle = (sessionId && sessionTitles[sessionId]) || 'Mezzofy AI';

  // ── Effects (must be before null guard — Rules of Hooks) ──────────────────

  useEffect(() => {
    scrollRef.current?.scrollToEnd({animated: true});
  }, [messages, isTyping]);

  useEffect(() => {
    if (recording) {
      timerRef.current = setInterval(
        () => setRecordTime(useChatStore.getState().recordTime + 1),
        1000,
      );
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      setRecordTime(0);
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [recording]);

  useEffect(() => {
    Voice.onSpeechResults = (e: SpeechResultsEvent) => {
      if (e.value?.[0]) {
        setLiveTranscript(e.value[0]);
      }
    };
    return () => {
      Voice.destroy().then(Voice.removeAllListeners);
    };
  }, []);

  // Poll for active task status while task is queued/running
  useEffect(() => {
    if (!sessionId) {return;}
    if (!activeTask || activeTask.status === 'completed' ||
        activeTask.status === 'failed' || activeTask.status === 'cancelled') {
      return;
    }
    const interval = setInterval(() => pollActiveTask(sessionId), 4000);
    return () => clearInterval(interval);
  }, [activeTask, sessionId, pollActiveTask]);

  // Auto-dismiss task bar 3 seconds after task completes
  useEffect(() => {
    if (activeTask?.status === 'completed') {
      const timer = setTimeout(() => clearActiveTask(), 3000);
      return () => clearTimeout(timer);
    }
  }, [activeTask?.status, clearActiveTask]);

  // ── Null guard AFTER all hooks ─────────────────────────────────────────────
  if (!user) {
    return null;
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  const formatSecs = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  // ── Actions ────────────────────────────────────────────────────────────────

  const handleSend = (
    text: string,
    mode = 'text',
    media: MediaInfo | null = null,
    uri: string | null = null,
  ) => {
    if (mode === 'myfiles') {
      if (!selectedArtifact) {return;}
      setInput('');
      setLiveTranscript('');
      sendArtifactToServer(selectedArtifact.id, text);
      setSelectedArtifact(null);
      setInputMode('text');
      return;
    }
    if (!text && !media) {
      return;
    }
    setInput('');
    setMediaPreview(null);
    setMediaUri(null);
    setLiveTranscript('');
    // sendToServer handles isTyping, optimistic user message, and API call
    sendToServer(text, mode, media, uri);
  };

  const handleNewChat = () => {
    resetChat();
    setSessionId(null);
    setEditingTitle(false);
  };

  const handleModeAction = async (mode: string) => {
    setInputMode(mode);
    setShowModes(false);

    if (mode === 'image') {
      launchImageLibrary({mediaType: 'photo', selectionLimit: 1}, response => {
        if (response.didCancel || response.errorCode || !response.assets?.length) {
          return;
        }
        const asset = response.assets[0];
        if (!asset.uri) {return;}
        setMediaUri(asset.uri);
        setMediaPreview({
          type: mode,
          name: asset.fileName || `media_${Date.now()}.jpg`,
          size: formatBytes(asset.fileSize),
          emoji: '📷',
          mimeType: asset.type || 'image/jpeg',
        });
      });
    } else if (mode === 'file') {
      try {
        const results = await DocumentPicker.pick({
          type: [DocTypes.allFiles],
        });
        const result = results[0];
        setMediaUri(result.uri);
        setMediaPreview({
          type: mode,
          name: result.name || `file_${Date.now()}`,
          size: result.size ? formatBytes(result.size) : '—',
          emoji: '📎',
          mimeType: result.type || 'application/octet-stream',
        });
      } catch (e) {
        if (!isDocPickerCancel(e)) {
          console.warn('DocumentPicker error:', e);
        }
      }
    } else if (mode === 'url') {
      setInput('https://');
    } else if (mode === 'camera') {
      navigation.navigate('Camera');
    } else if (mode === 'myfiles') {
      setShowMyFilesModal(true);
      setMyFilesLoading(true);
      setMyFilesError(null);
      try {
        const result = await listFilesApi('personal');
        setMyFilesList(result.artifacts);
      } catch {
        setMyFilesError('Failed to load files. Please try again.');
      } finally {
        setMyFilesLoading(false);
      }
    }
  };

  const handleStartRecording = async () => {
    setLiveTranscript('');
    setRecording(true);
    try {
      const locale = SPEECH_LOCALE[speechLanguage] ?? 'en-US';
      await Voice.start(locale);
    } catch (e) {
      console.warn('Voice.start error:', e);
    }
  };

  const handleStopRecording = async () => {
    try {
      await Voice.stop();
    } catch (e) {
      console.warn('Voice.stop error:', e);
    }
    setRecording(false);
    const transcript = liveTranscript || useChatStore.getState().mediaPreview?.name || '';
    if (transcript) {
      setInput(transcript);
      setInputMode('text');
    }
  };

  // ── Render helpers ─────────────────────────────────────────────────────────

  const renderMessage = (msg: Message) => {
    const isUser = msg.role === 'user';
    return (
      <View key={msg.id} style={[styles.msgRow, isUser && styles.msgRowUser]}>
        <View style={{maxWidth: '82%'}}>
          {msg.media && (
            <View style={[
              styles.mediaTag,
              isUser
                ? {backgroundColor: colors.accent + '22', borderColor: colors.accent + '33'}
                : {backgroundColor: colors.surfaceLight, borderColor: colors.border},
            ]}>
              <Text style={styles.mediaEmoji}>{msg.media.emoji}</Text>
              <Text style={[styles.mediaName, {color: colors.text}]}>{msg.media.name}</Text>
              <Text style={[styles.mediaSize, {color: colors.textMuted}]}>{msg.media.size}</Text>
            </View>
          )}
          <View
            style={[
              styles.bubble,
              isUser ? styles.bubbleUser : styles.bubbleAI,
              isUser
                ? {backgroundColor: colors.accent}
                : {backgroundColor: colors.surfaceLight, borderWidth: 1, borderColor: colors.border},
              msg.media && styles.bubbleWithMedia,
            ]}>
            <Text style={[styles.bubbleText, isUser ? styles.bubbleTextUser : {color: colors.text}]}>
              {msg.text}
            </Text>
          </View>
          {msg.artifacts?.map((a, i) => {
            const ts = FILE_TYPE_STYLES[a.type] || FILE_TYPE_STYLES.md;
            return (
              <View key={i} style={[styles.artifactCard, {backgroundColor: colors.card, borderColor: colors.border}]}>
                <View style={[styles.artifactIcon, {backgroundColor: ts.bg}]}>
                  <Text style={[styles.artifactLabel, {color: ts.color}]}>{ts.label}</Text>
                </View>
                <View style={{flex: 1}}>
                  <Text style={[styles.artifactName, {color: colors.text}]} numberOfLines={1}>
                    {a.name}
                  </Text>
                  <Text style={[styles.artifactSize, {color: colors.textMuted}]}>
                    {a.download_url ? 'Available' : 'Processing...'}
                  </Text>
                </View>
                <Icon name="download-outline" size={16} color={colors.accent} />
              </View>
            );
          })}
          {msg.tools && (
            <View style={styles.toolsRow}>
              {msg.tools.map((t, i) => (
                <View key={i} style={[styles.toolBadge, {backgroundColor: colors.accent + '12', borderColor: colors.accent + '22'}]}>
                  <Text style={[styles.toolText, {color: colors.accent}]}>{t}</Text>
                </View>
              ))}
            </View>
          )}
          <Text style={[styles.time, {color: colors.textDim}, isUser && styles.timeUser]}>{msg.time}</Text>
        </View>
      </View>
    );
  };

  // ── JSX ────────────────────────────────────────────────────────────────────

  return (
    <KeyboardAvoidingView
      style={[styles.container, {backgroundColor: colors.primary}]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {/* Header */}
      <View style={[styles.header, {borderBottomColor: colors.border}]}>
        <View style={styles.headerLeft}>
          <View style={styles.headerTop}>
            {editingTitle ? (
              <TextInput
                ref={titleInputRef}
                value={currentTitle === 'Mezzofy AI' ? '' : currentTitle}
                onChangeText={t => {
                  if (sessionId) {setSessionTitle(sessionId, t);}
                }}
                onBlur={() => setEditingTitle(false)}
                onSubmitEditing={() => setEditingTitle(false)}
                placeholder="Chat title..."
                placeholderTextColor={colors.textDim}
                style={[styles.headerTitleInput, {color: colors.text, borderBottomColor: colors.accent}]}
                returnKeyType="done"
                autoFocus
              />
            ) : (
              <Text style={[styles.headerTitle, {color: colors.text}]} numberOfLines={1}>
                {currentTitle}
              </Text>
            )}
            {sessionId && !editingTitle && (
              <TouchableOpacity
                onPress={() => setEditingTitle(true)}
                style={styles.editTitleBtn}>
                <Icon name="pencil-outline" size={14} color={colors.textMuted} />
              </TouchableOpacity>
            )}
          </View>
          <View style={styles.headerSubRow}>
            <DeptBadge dept={user.department} compact />
            <Text style={[styles.headerSub, {color: colors.textMuted}]}>
              {user.name} · {user.role.replace('_', ' ')}
            </Text>
          </View>
        </View>
        <TouchableOpacity
          style={[styles.newChatBtn, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}
          onPress={handleNewChat}>
          <Icon name="add" size={18} color={colors.accent} />
        </TouchableOpacity>
      </View>

      {/* Messages */}
      <ScrollView
        ref={scrollRef}
        style={styles.msgList}
        contentContainerStyle={{paddingBottom: 16}}>
        {messages.map(renderMessage)}
        {isTyping && (
          <View style={styles.typingWrap}>
            <View style={[styles.typingBubble, {backgroundColor: colors.surfaceLight, borderColor: colors.border}]}>
              <View style={styles.dots}>
                {[0, 1, 2].map(i => (
                  <View key={i} style={[styles.dot, {backgroundColor: colors.accent, opacity: 0.4 + i * 0.3}]} />
                ))}
              </View>
              <Text style={[styles.typingText, {color: colors.textMuted}]}>Thinking...</Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* API Error Banner */}
      {chatError ? (
        <View style={[styles.errorBanner, {backgroundColor: colors.danger + '14', borderColor: colors.danger + '30'}]}>
          <Icon name="alert-circle-outline" size={14} color={colors.danger} />
          <Text style={[styles.errorBannerText, {color: colors.danger}]} numberOfLines={2}>
            {normalizeApiError(chatError)}
          </Text>
          <TouchableOpacity onPress={clearError} style={styles.errorBannerClose}>
            <Text style={[styles.errorBannerCloseText, {color: colors.danger}]}>✕</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {/* Media Preview */}
      {mediaPreview && (
        <View style={[styles.previewBar, {backgroundColor: colors.card, borderColor: colors.border}]}>
          <Text style={styles.previewEmoji}>{mediaPreview.emoji}</Text>
          <View style={{flex: 1}}>
            <Text style={[styles.previewName, {color: colors.text}]}>{mediaPreview.name}</Text>
            <Text style={[styles.previewSize, {color: colors.textMuted}]}>{mediaPreview.size}</Text>
          </View>
          <TouchableOpacity
            onPress={() => {
              setMediaPreview(null);
              setMediaUri(null);
              setInputMode('text');
            }}>
            <Text style={[styles.previewClose, {color: colors.textMuted}]}>✕</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* My Files: Selected Artifact Preview */}
      {selectedArtifact && (
        <View style={[styles.previewBar, {backgroundColor: colors.card, borderColor: colors.border}]}>
          <Text style={styles.previewEmoji}>📂</Text>
          <View style={{flex: 1}}>
            <Text style={[styles.previewName, {color: colors.text}]} numberOfLines={1}>
              {selectedArtifact.filename}
            </Text>
            <Text style={[styles.previewSize, {color: colors.textMuted}]}>
              {selectedArtifact.file_type.toUpperCase()} · From My Files
            </Text>
          </View>
          <TouchableOpacity
            onPress={() => {
              setSelectedArtifact(null);
              setInputMode('text');
            }}>
            <Text style={[styles.previewClose, {color: colors.textMuted}]}>✕</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Active Task Bar */}
      {activeTask && activeTask.session_id === sessionId && (
        <View style={styles.taskBar}>
          {activeTask.status === 'completed' ? (
            <Icon name="checkmark-circle" size={16} color="#fff" />
          ) : activeTask.status === 'failed' ? (
            <Icon name="close-circle" size={16} color="#fff" />
          ) : (
            <ActivityIndicator size="small" color="#fff" />
          )}
          <View style={{flex: 1, overflow: 'hidden', justifyContent: 'center'}}>
            <Text style={styles.taskBarText} numberOfLines={1}>
              {'TASK #'}{activeTask.id.slice(0, 8).toUpperCase()}{'  '}{activeTask.status.toUpperCase()}
              {activeTask.progress != null && activeTask.progress > 0
                ? `  ${activeTask.progress}%`
                : ''}
            </Text>
            {activeTask.status === 'running' && (() => {
              try {
                const step = activeTask.current_step
                  ? JSON.parse(activeTask.current_step)
                  : null;
                const desc = step?.description;
                return desc ? (
                  <Text style={[styles.taskBarText, {fontSize: 10, opacity: 0.8}]} numberOfLines={1}>
                    {desc}
                  </Text>
                ) : null;
              } catch {
                return null;
              }
            })()}
          </View>
          <TouchableOpacity onPress={clearActiveTask} hitSlop={{top: 8, bottom: 8, left: 8, right: 8}}>
            <Icon name="close" size={14} color="#fff" />
          </TouchableOpacity>
        </View>
      )}

      {/* Input Mode Selector Grid */}
      {showModes && (
        <View style={[styles.modeGrid, {backgroundColor: colors.card, borderColor: colors.border}]}>
          {INPUT_MODES.map(m => (
            <TouchableOpacity
              key={m.id}
              onPress={() => handleModeAction(m.id)}
              style={[
                styles.modeBtn,
                inputMode === m.id && {
                  backgroundColor: m.color + '22',
                  borderColor: m.color + '44',
                },
              ]}>
              <Icon name={m.icon} size={20} color={m.color} />
              <Text style={[styles.modeLbl, {color: colors.textMuted}]}>{m.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Speech Recording UI */}
      {recording && (
        <View style={[styles.recordPanel, {backgroundColor: colors.card, borderColor: colors.danger + '33'}]}>
          <View style={[styles.recordMic, {backgroundColor: colors.danger + '22'}]}>
            <Icon name="mic" size={28} color={colors.danger} />
          </View>
          <Text style={[styles.recordTimer, {color: colors.text}]}>{formatSecs(recordTime)}</Text>
          <Text style={[styles.recordHint, {color: colors.textMuted}]}>
            {liveTranscript || 'Listening...'}
          </Text>
          <TouchableOpacity
            onPress={handleStopRecording}
            style={[styles.recordStop, {backgroundColor: colors.danger}]}>
            <Icon name="stop" size={16} color="#fff" />
            <Text style={styles.recordStopText}>Stop & Edit</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Input Bar */}
      {!recording && (
        <View style={[styles.inputBar, {borderTopColor: colors.border}]}>
          <TouchableOpacity
            onPress={() => setShowModes(!showModes)}
            style={[
              styles.plusBtn,
              {backgroundColor: colors.surfaceLight, borderColor: colors.border},
              showModes && {backgroundColor: colors.accent + '22', borderColor: colors.accent + '44'},
            ]}>
            <Icon
              name="add"
              size={20}
              color={showModes ? colors.accent : colors.textMuted}
            />
          </TouchableOpacity>

          {inputMode === 'speech' ? (
            <TouchableOpacity
              onPressIn={handleStartRecording}
              style={[styles.holdBtn, {borderColor: colors.accent + '44', backgroundColor: colors.accentSoft}]}>
              <Text style={[styles.holdBtnText, {color: colors.accent}]}>🎤 Hold to Speak</Text>
            </TouchableOpacity>
          ) : (
            <TextInput
              value={input}
              onChangeText={setInput}
              editable={!isTyping}
              onSubmitEditing={() => {
                if (!isTyping) {handleSend(input, inputMode, mediaPreview, mediaUri);}
              }}
              placeholder={
                inputMode === 'url'
                  ? 'Paste URL to analyze...'
                  : mediaPreview
                  ? 'Add a message (optional)...'
                  : 'Message Mezzofy AI...'
              }
              placeholderTextColor={colors.textDim}
              style={[
                styles.textInput,
                {backgroundColor: colors.surfaceLight, borderColor: colors.border, color: colors.text},
                isTyping && styles.textInputDisabled,
              ]}
              returnKeyType="send"
            />
          )}

          <TouchableOpacity
            onPress={() => {
              if (!isTyping) {handleSend(input, inputMode, mediaPreview, mediaUri);}
            }}
            disabled={isTyping}
            style={[
              styles.sendBtn,
              {backgroundColor: colors.accent, shadowColor: colors.accent},
              isTyping && {opacity: 0.4},
            ]}>
            <Icon name="send" size={18} color="#fff" />
          </TouchableOpacity>
        </View>
      )}
      {/* My Files Browser Modal */}
      <Modal
        visible={showMyFilesModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowMyFilesModal(false)}>
        <TouchableOpacity
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowMyFilesModal(false)}
        />
        <View style={[styles.modalSheet, {backgroundColor: colors.card, borderColor: colors.border}]}>
          <View style={[styles.modalHeader, {borderBottomColor: colors.border}]}>
            <Text style={[styles.modalTitle, {color: colors.text}]}>My Files</Text>
            <TouchableOpacity onPress={() => setShowMyFilesModal(false)}>
              <Text style={[styles.previewClose, {color: colors.textMuted}]}>✕</Text>
            </TouchableOpacity>
          </View>

          {myFilesLoading ? (
            <ActivityIndicator size="large" color={colors.accent} style={{marginTop: 32}} />
          ) : myFilesError ? (
            <Text style={[styles.modalError, {color: colors.danger}]}>{myFilesError}</Text>
          ) : myFilesList.length === 0 ? (
            <Text style={[styles.modalEmpty, {color: colors.textMuted}]}>
              No files found. Upload files in the Files tab.
            </Text>
          ) : (
            <ScrollView style={styles.modalList}>
              {myFilesList.map(item => {
                const ext = item.file_type.toLowerCase();
                const ts = (FILE_TYPE_STYLES as Record<string, {bg: string; color: string; label: string}>)[ext]
                  || {bg: '#4DA6FF18', color: '#4DA6FF', label: ext.toUpperCase().slice(0, 4) || 'FILE'};
                const date = new Date(item.created_at).toLocaleDateString([], {
                  month: 'short', day: 'numeric', year: 'numeric',
                });
                return (
                  <TouchableOpacity
                    key={item.id}
                    style={[styles.modalFileRow, {borderBottomColor: colors.border}]}
                    onPress={() => {
                      setSelectedArtifact({id: item.id, filename: item.filename, file_type: item.file_type});
                      setInputMode('myfiles');
                      setShowMyFilesModal(false);
                    }}>
                    <View style={[styles.modalFileIcon, {backgroundColor: ts.bg}]}>
                      <Text style={[styles.modalFileLabel, {color: ts.color}]}>{ts.label}</Text>
                    </View>
                    <View style={{flex: 1}}>
                      <Text style={[styles.modalFileName, {color: colors.text}]} numberOfLines={1}>
                        {item.filename}
                      </Text>
                      <Text style={[styles.modalFileDate, {color: colors.textMuted}]}>{date}</Text>
                    </View>
                    <Icon name="chevron-forward-outline" size={16} color={colors.textMuted} />
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          )}
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  header: {flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, paddingTop: 8, borderBottomWidth: 1},
  headerLeft: {flex: 1, marginRight: 12},
  headerTop: {flexDirection: 'row', alignItems: 'center', gap: 8},
  headerTitle: {fontSize: 20, fontWeight: '800', flexShrink: 1},
  headerTitleInput: {flex: 1, fontSize: 18, fontWeight: '700', borderBottomWidth: 1, paddingVertical: 2, paddingHorizontal: 0},
  editTitleBtn: {padding: 4},
  headerSubRow: {flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2},
  headerSub: {fontSize: 12},
  newChatBtn: {borderWidth: 1, borderRadius: 12, padding: 10},
  msgList: {flex: 1, paddingHorizontal: 16, paddingTop: 16},
  msgRow: {marginBottom: 16},
  msgRowUser: {alignItems: 'flex-end'},
  mediaTag: {flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingVertical: 10, borderTopLeftRadius: 14, borderTopRightRadius: 14, borderWidth: 1, borderBottomWidth: 0},
  mediaEmoji: {fontSize: 18},
  mediaName: {fontWeight: '600', fontSize: 13},
  mediaSize: {fontSize: 12, opacity: 0.6},
  bubble: {padding: 12, paddingHorizontal: 16},
  bubbleUser: {borderRadius: 18, borderBottomRightRadius: 4},
  bubbleAI: {borderRadius: 18, borderBottomLeftRadius: 4},
  bubbleWithMedia: {borderTopLeftRadius: 0, borderTopRightRadius: 0},
  bubbleText: {fontSize: 14, lineHeight: 21},
  bubbleTextUser: {color: '#fff'},
  artifactCard: {flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderRadius: 12, padding: 10, paddingHorizontal: 14, marginTop: 8},
  artifactIcon: {width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center'},
  artifactLabel: {fontSize: 11, fontWeight: '800'},
  artifactName: {fontSize: 13, fontWeight: '600'},
  artifactSize: {fontSize: 11, marginTop: 1},
  toolsRow: {flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 6},
  toolBadge: {borderWidth: 1, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2},
  toolText: {fontSize: 10, fontWeight: '600'},
  time: {fontSize: 10, marginTop: 4},
  timeUser: {textAlign: 'right'},
  errorBanner: {flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 16, marginBottom: 6, padding: 10, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1},
  errorBannerText: {flex: 1, fontSize: 12, lineHeight: 17},
  errorBannerClose: {padding: 4},
  errorBannerCloseText: {fontSize: 14},
  typingWrap: {marginBottom: 16},
  typingBubble: {flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 18, borderBottomLeftRadius: 4, padding: 14, paddingHorizontal: 20, borderWidth: 1, alignSelf: 'flex-start'},
  dots: {flexDirection: 'row', gap: 4},
  dot: {width: 7, height: 7, borderRadius: 3.5},
  typingText: {fontSize: 12, marginLeft: 6},
  previewBar: {flexDirection: 'row', alignItems: 'center', gap: 10, marginHorizontal: 16, padding: 10, paddingHorizontal: 14, borderRadius: 14, borderWidth: 1, marginBottom: 8},
  previewEmoji: {fontSize: 22},
  previewName: {fontSize: 13, fontWeight: '600'},
  previewSize: {fontSize: 11},
  previewClose: {fontSize: 18, padding: 4},
  modeGrid: {flexDirection: 'row', flexWrap: 'wrap', gap: 8, margin: 16, marginTop: 8, padding: 12, borderRadius: 16, borderWidth: 1},
  modeBtn: {width: '22%', alignItems: 'center', gap: 6, paddingVertical: 12, borderRadius: 12, borderWidth: 1, borderColor: 'transparent'},
  modeLbl: {fontSize: 10, fontWeight: '600'},
  recordPanel: {margin: 16, padding: 20, borderRadius: 16, borderWidth: 1, alignItems: 'center', gap: 12},
  recordMic: {width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center'},
  recordTimer: {fontSize: 22, fontWeight: '700', fontVariant: ['tabular-nums']},
  recordHint: {fontSize: 12, textAlign: 'center', paddingHorizontal: 16},
  recordStop: {flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 12, paddingHorizontal: 32, paddingVertical: 10},
  recordStopText: {color: '#fff', fontSize: 14, fontWeight: '700'},
  taskBar: {flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#f97316', paddingHorizontal: 16, height: 40},
  taskBarText: {flex: 1, color: '#fff', fontSize: 12, fontWeight: '600'},
  inputBar: {flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, paddingTop: 10, borderTopWidth: 1},
  plusBtn: {borderWidth: 1, borderRadius: 12, width: 48, height: 48, alignItems: 'center', justifyContent: 'center'},
  holdBtn: {flex: 1, padding: 14, borderRadius: 14, borderWidth: 2, borderStyle: 'dashed', alignItems: 'center'},
  holdBtnText: {fontSize: 14, fontWeight: '600'},
  textInput: {flex: 1, paddingVertical: 13, paddingHorizontal: 16, borderRadius: 14, borderWidth: 1, fontSize: 14, minHeight: 48},
  textInputDisabled: {opacity: 0.5},
  sendBtn: {borderRadius: 12, width: 48, height: 48, alignItems: 'center', justifyContent: 'center', shadowOffset: {width: 0, height: 2}, shadowOpacity: 0.4, shadowRadius: 12, elevation: 6},
  // My Files modal
  modalOverlay: {position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)'},
  modalSheet: {position: 'absolute', bottom: 0, left: 0, right: 0, borderTopLeftRadius: 20, borderTopRightRadius: 20, borderWidth: 1, maxHeight: '70%'},
  modalHeader: {flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, paddingBottom: 12, borderBottomWidth: 1},
  modalTitle: {fontSize: 17, fontWeight: '700'},
  modalList: {flex: 1},
  modalFileRow: {flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1},
  modalFileIcon: {width: 40, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center'},
  modalFileLabel: {fontSize: 10, fontWeight: '800'},
  modalFileName: {fontSize: 14, fontWeight: '600'},
  modalFileDate: {fontSize: 12, marginTop: 2},
  modalError: {margin: 24, fontSize: 14, textAlign: 'center'},
  modalEmpty: {margin: 24, fontSize: 14, textAlign: 'center'},
});
