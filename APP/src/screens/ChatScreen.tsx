import React, {useState, useRef, useEffect} from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  StyleSheet, KeyboardAvoidingView, Platform,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {launchImageLibrary, MediaType} from 'react-native-image-picker';
import DocumentPicker, {types as DocTypes, isCancel as isDocPickerCancel} from 'react-native-document-picker';
import Voice, {SpeechResultsEvent} from '@react-native-voice/voice';
import {BRAND, INPUT_MODES, FILE_TYPE_STYLES} from '../utils/theme';
import {useAuthStore} from '../stores/authStore';
import {useChatStore, Message, MediaInfo} from '../stores/chatStore';
import {DeptBadge} from '../components/shared/DeptBadge';

const formatBytes = (bytes?: number): string => {
  if (!bytes) {return '—';}
  if (bytes < 1024) {return `${bytes} B`;}
  if (bytes < 1024 * 1024) {return `${(bytes / 1024).toFixed(1)} KB`;}
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const ChatScreen: React.FC<{navigation: any}> = ({navigation}) => {
  // ── All hooks MUST be called unconditionally (Rules of Hooks) ──────────────
  const user = useAuthStore(s => s.user);
  const {
    messages, isTyping, inputMode, showModes, recording, recordTime,
    mediaPreview, error: chatError,
    setInputMode, setShowModes, setRecording, setRecordTime, setMediaPreview,
    sendToServer, clearError, resetChat, setSessionId,
  } = useChatStore();
  const [input, setInput] = useState('');
  const [mediaUri, setMediaUri] = useState<string | null>(null);
  const [liveTranscript, setLiveTranscript] = useState('');
  const scrollRef = useRef<ScrollView>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
  };

  const handleModeAction = async (mode: string) => {
    setInputMode(mode);
    setShowModes(false);

    if (mode === 'image' || mode === 'video') {
      const mediaType: MediaType = mode === 'image' ? 'photo' : 'video';
      launchImageLibrary({mediaType, selectionLimit: 1}, response => {
        if (response.didCancel || response.errorCode || !response.assets?.length) {
          return;
        }
        const asset = response.assets[0];
        if (!asset.uri) {return;}
        setMediaUri(asset.uri);
        setMediaPreview({
          type: mode,
          name: asset.fileName || `media_${Date.now()}.${mode === 'image' ? 'jpg' : 'mp4'}`,
          size: formatBytes(asset.fileSize),
          emoji: mode === 'image' ? '📷' : '🎥',
          mimeType: asset.type || (mode === 'image' ? 'image/jpeg' : 'video/mp4'),
        });
      });
    } else if (mode === 'file' || mode === 'audio') {
      try {
        const results = await DocumentPicker.pick({
          type: mode === 'audio' ? [DocTypes.audio] : [DocTypes.allFiles],
        });
        const result = results[0];
        setMediaUri(result.uri);
        setMediaPreview({
          type: mode,
          name: result.name || `file_${Date.now()}`,
          size: result.size ? formatBytes(result.size) : '—',
          emoji: mode === 'audio' ? '🔊' : '📎',
          mimeType: result.type || (mode === 'audio' ? 'audio/m4a' : 'application/octet-stream'),
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
    }
  };

  const handleStartRecording = async () => {
    setLiveTranscript('');
    setRecording(true);
    try {
      await Voice.start('en-US');
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
      handleSend(
        transcript,
        'speech',
        {type: 'speech', name: 'Voice message', size: formatSecs(recordTime), emoji: '🎤'},
      );
    }
  };

  // ── Render helpers ─────────────────────────────────────────────────────────

  const renderMessage = (msg: Message) => {
    const isUser = msg.role === 'user';
    return (
      <View key={msg.id} style={[styles.msgRow, isUser && styles.msgRowUser]}>
        <View style={{maxWidth: '82%'}}>
          {msg.media && (
            <View style={[styles.mediaTag, isUser ? styles.mediaTagUser : styles.mediaTagAI]}>
              <Text style={styles.mediaEmoji}>{msg.media.emoji}</Text>
              <Text style={styles.mediaName}>{msg.media.name}</Text>
              <Text style={styles.mediaSize}>{msg.media.size}</Text>
            </View>
          )}
          <View
            style={[
              styles.bubble,
              isUser ? styles.bubbleUser : styles.bubbleAI,
              msg.media && styles.bubbleWithMedia,
            ]}>
            <Text style={[styles.bubbleText, isUser && styles.bubbleTextUser]}>
              {msg.text}
            </Text>
          </View>
          {msg.artifacts?.map((a, i) => {
            const ts = FILE_TYPE_STYLES[a.type] || FILE_TYPE_STYLES.md;
            return (
              <View key={i} style={styles.artifactCard}>
                <View style={[styles.artifactIcon, {backgroundColor: ts.bg}]}>
                  <Text style={[styles.artifactLabel, {color: ts.color}]}>{ts.label}</Text>
                </View>
                <View style={{flex: 1}}>
                  <Text style={styles.artifactName} numberOfLines={1}>
                    {a.name}
                  </Text>
                  <Text style={styles.artifactSize}>
                    {a.download_url ? 'Available' : 'Processing...'}
                  </Text>
                </View>
                <Icon name="download-outline" size={16} color={BRAND.accent} />
              </View>
            );
          })}
          {msg.tools && (
            <View style={styles.toolsRow}>
              {msg.tools.map((t, i) => (
                <View key={i} style={styles.toolBadge}>
                  <Text style={styles.toolText}>{t}</Text>
                </View>
              ))}
            </View>
          )}
          <Text style={[styles.time, isUser && styles.timeUser]}>{msg.time}</Text>
        </View>
      </View>
    );
  };

  // ── JSX ────────────────────────────────────────────────────────────────────

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <View style={styles.headerTop}>
            <Text style={styles.headerTitle}>Mezzofy AI</Text>
            <DeptBadge dept={user.department} compact />
          </View>
          <Text style={styles.headerSub}>
            {user.name} · {user.role.replace('_', ' ')}
          </Text>
        </View>
        <TouchableOpacity style={styles.newChatBtn} onPress={handleNewChat}>
          <Icon name="add" size={18} color={BRAND.accent} />
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
            <View style={styles.typingBubble}>
              <View style={styles.dots}>
                {[0, 1, 2].map(i => (
                  <View key={i} style={[styles.dot, {opacity: 0.4 + i * 0.3}]} />
                ))}
              </View>
              <Text style={styles.typingText}>Thinking...</Text>
            </View>
          </View>
        )}
      </ScrollView>

      {/* API Error Banner */}
      {chatError ? (
        <View style={styles.errorBanner}>
          <Icon name="alert-circle-outline" size={14} color={BRAND.danger} />
          <Text style={styles.errorBannerText} numberOfLines={2}>
            {chatError}
          </Text>
          <TouchableOpacity onPress={clearError} style={styles.errorBannerClose}>
            <Text style={styles.errorBannerCloseText}>✕</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {/* Media Preview */}
      {mediaPreview && (
        <View style={styles.previewBar}>
          <Text style={styles.previewEmoji}>{mediaPreview.emoji}</Text>
          <View style={{flex: 1}}>
            <Text style={styles.previewName}>{mediaPreview.name}</Text>
            <Text style={styles.previewSize}>{mediaPreview.size}</Text>
          </View>
          <TouchableOpacity
            onPress={() => {
              setMediaPreview(null);
              setMediaUri(null);
              setInputMode('text');
            }}>
            <Text style={styles.previewClose}>✕</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Input Mode Selector Grid */}
      {showModes && (
        <View style={styles.modeGrid}>
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
              <Text style={styles.modeLbl}>{m.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Speech Recording UI */}
      {recording && (
        <View style={styles.recordPanel}>
          <View style={styles.recordMic}>
            <Icon name="mic" size={28} color={BRAND.danger} />
          </View>
          <Text style={styles.recordTimer}>{formatSecs(recordTime)}</Text>
          <Text style={styles.recordHint}>
            {liveTranscript || 'Listening...'}
          </Text>
          <TouchableOpacity
            onPress={handleStopRecording}
            style={styles.recordStop}>
            <Icon name="stop" size={16} color="#fff" />
            <Text style={styles.recordStopText}>Stop & Send</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Input Bar */}
      {!recording && (
        <View style={styles.inputBar}>
          <TouchableOpacity
            onPress={() => setShowModes(!showModes)}
            style={[styles.plusBtn, showModes && styles.plusBtnActive]}>
            <Icon
              name="add"
              size={20}
              color={showModes ? BRAND.accent : BRAND.textMuted}
            />
          </TouchableOpacity>

          {inputMode === 'speech' ? (
            <TouchableOpacity
              onPressIn={handleStartRecording}
              style={styles.holdBtn}>
              <Text style={styles.holdBtnText}>🎤 Hold to Speak</Text>
            </TouchableOpacity>
          ) : (
            <TextInput
              value={input}
              onChangeText={setInput}
              editable={!isTyping}
              onSubmitEditing={() => {
                if (!isTyping) handleSend(input, inputMode, mediaPreview, mediaUri);
              }}
              placeholder={
                inputMode === 'url'
                  ? 'Paste URL to analyze...'
                  : mediaPreview
                  ? 'Add a message (optional)...'
                  : 'Message Mezzofy AI...'
              }
              placeholderTextColor={BRAND.textDim}
              style={[styles.textInput, isTyping && styles.textInputDisabled]}
              returnKeyType="send"
            />
          )}

          <TouchableOpacity
            onPress={() => {
              if (!isTyping) handleSend(input, inputMode, mediaPreview, mediaUri);
            }}
            disabled={isTyping}
            style={[styles.sendBtn, isTyping && {opacity: 0.4}]}>
            <Icon name="send" size={18} color="#fff" />
          </TouchableOpacity>
        </View>
      )}
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: BRAND.primary},
  header: {flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, paddingTop: 8, borderBottomWidth: 1, borderBottomColor: BRAND.border},
  headerTop: {flexDirection: 'row', alignItems: 'center', gap: 10},
  headerTitle: {color: BRAND.text, fontSize: 20, fontWeight: '800'},
  headerSub: {color: BRAND.textMuted, fontSize: 12, marginTop: 2},
  newChatBtn: {backgroundColor: BRAND.surfaceLight, borderWidth: 1, borderColor: BRAND.border, borderRadius: 12, padding: 10},
  msgList: {flex: 1, paddingHorizontal: 16, paddingTop: 16},
  msgRow: {marginBottom: 16},
  msgRowUser: {alignItems: 'flex-end'},
  mediaTag: {flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingVertical: 10, borderTopLeftRadius: 14, borderTopRightRadius: 14, borderWidth: 1, borderBottomWidth: 0},
  mediaTagUser: {backgroundColor: BRAND.accent + '22', borderColor: BRAND.accent + '33'},
  mediaTagAI: {backgroundColor: BRAND.surfaceLight, borderColor: BRAND.border},
  mediaEmoji: {fontSize: 18},
  mediaName: {fontWeight: '600', color: BRAND.text, fontSize: 13},
  mediaSize: {color: BRAND.textMuted, fontSize: 12, opacity: 0.6},
  bubble: {padding: 12, paddingHorizontal: 16},
  bubbleUser: {backgroundColor: BRAND.accent, borderRadius: 18, borderBottomRightRadius: 4},
  bubbleAI: {backgroundColor: BRAND.surfaceLight, borderRadius: 18, borderBottomLeftRadius: 4, borderWidth: 1, borderColor: BRAND.border},
  bubbleWithMedia: {borderTopLeftRadius: 0, borderTopRightRadius: 0},
  bubbleText: {color: BRAND.text, fontSize: 14, lineHeight: 21},
  bubbleTextUser: {color: '#fff'},
  artifactCard: {flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: BRAND.card, borderWidth: 1, borderColor: BRAND.border, borderRadius: 12, padding: 10, paddingHorizontal: 14, marginTop: 8},
  artifactIcon: {width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center'},
  artifactLabel: {fontSize: 11, fontWeight: '800'},
  artifactName: {color: BRAND.text, fontSize: 13, fontWeight: '600'},
  artifactSize: {color: BRAND.textMuted, fontSize: 11, marginTop: 1},
  toolsRow: {flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 6},
  toolBadge: {backgroundColor: BRAND.accent + '12', borderWidth: 1, borderColor: BRAND.accent + '22', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2},
  toolText: {fontSize: 10, color: BRAND.accent, fontWeight: '600'},
  time: {fontSize: 10, color: BRAND.textDim, marginTop: 4},
  timeUser: {textAlign: 'right'},
  errorBanner: {flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 16, marginBottom: 6, padding: 10, paddingHorizontal: 14, borderRadius: 12, backgroundColor: BRAND.danger + '14', borderWidth: 1, borderColor: BRAND.danger + '30'},
  errorBannerText: {flex: 1, color: BRAND.danger, fontSize: 12, lineHeight: 17},
  errorBannerClose: {padding: 4},
  errorBannerCloseText: {color: BRAND.danger, fontSize: 14},
  typingWrap: {marginBottom: 16},
  typingBubble: {flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: BRAND.surfaceLight, borderRadius: 18, borderBottomLeftRadius: 4, padding: 14, paddingHorizontal: 20, borderWidth: 1, borderColor: BRAND.border, alignSelf: 'flex-start'},
  dots: {flexDirection: 'row', gap: 4},
  dot: {width: 7, height: 7, borderRadius: 3.5, backgroundColor: BRAND.accent},
  typingText: {fontSize: 12, color: BRAND.textMuted, marginLeft: 6},
  previewBar: {flexDirection: 'row', alignItems: 'center', gap: 10, marginHorizontal: 16, padding: 10, paddingHorizontal: 14, borderRadius: 14, backgroundColor: BRAND.card, borderWidth: 1, borderColor: BRAND.border, marginBottom: 8},
  previewEmoji: {fontSize: 22},
  previewName: {color: BRAND.text, fontSize: 13, fontWeight: '600'},
  previewSize: {color: BRAND.textMuted, fontSize: 11},
  previewClose: {color: BRAND.textMuted, fontSize: 18, padding: 4},
  modeGrid: {flexDirection: 'row', flexWrap: 'wrap', gap: 8, margin: 16, marginTop: 8, padding: 12, backgroundColor: BRAND.card, borderRadius: 16, borderWidth: 1, borderColor: BRAND.border},
  modeBtn: {width: '22%', alignItems: 'center', gap: 6, paddingVertical: 12, borderRadius: 12, borderWidth: 1, borderColor: 'transparent'},
  modeLbl: {fontSize: 10, color: BRAND.textMuted, fontWeight: '600'},
  recordPanel: {margin: 16, padding: 20, borderRadius: 16, backgroundColor: BRAND.card, borderWidth: 1, borderColor: BRAND.danger + '33', alignItems: 'center', gap: 12},
  recordMic: {width: 64, height: 64, borderRadius: 32, backgroundColor: BRAND.danger + '22', alignItems: 'center', justifyContent: 'center'},
  recordTimer: {color: BRAND.text, fontSize: 22, fontWeight: '700', fontVariant: ['tabular-nums']},
  recordHint: {color: BRAND.textMuted, fontSize: 12, textAlign: 'center', paddingHorizontal: 16},
  recordStop: {flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: BRAND.danger, borderRadius: 12, paddingHorizontal: 32, paddingVertical: 10},
  recordStopText: {color: '#fff', fontSize: 14, fontWeight: '700'},
  inputBar: {flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: BRAND.border},
  plusBtn: {backgroundColor: BRAND.surfaceLight, borderWidth: 1, borderColor: BRAND.border, borderRadius: 12, width: 48, height: 48, alignItems: 'center', justifyContent: 'center'},
  plusBtnActive: {backgroundColor: BRAND.accent + '22', borderColor: BRAND.accent + '44'},
  holdBtn: {flex: 1, padding: 14, borderRadius: 14, borderWidth: 2, borderColor: BRAND.accent + '44', borderStyle: 'dashed', backgroundColor: BRAND.accentSoft, alignItems: 'center'},
  holdBtnText: {color: BRAND.accent, fontSize: 14, fontWeight: '600'},
  textInput: {flex: 1, paddingVertical: 13, paddingHorizontal: 16, borderRadius: 14, backgroundColor: BRAND.surfaceLight, borderWidth: 1, borderColor: BRAND.border, color: BRAND.text, fontSize: 14, minHeight: 48},
  textInputDisabled: {opacity: 0.5},
  sendBtn: {backgroundColor: BRAND.accent, borderRadius: 12, width: 48, height: 48, alignItems: 'center', justifyContent: 'center', shadowColor: BRAND.accent, shadowOffset: {width: 0, height: 2}, shadowOpacity: 0.4, shadowRadius: 12, elevation: 6},
});
