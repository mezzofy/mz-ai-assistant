import React, {useState, useEffect} from 'react';
import {View, Text, TouchableOpacity, StyleSheet, Image, PermissionsAndroid, Platform} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {launchCamera} from 'react-native-image-picker';
import {useTheme} from '../hooks/useTheme';
import {mzWs} from '../api/websocket';

export const CameraScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [wsError, setWsError] = useState<string | null>(null);
  const [capturedUri, setCapturedUri] = useState<string | null>(null);
  const colors = useTheme();

  // Connect mzWs on mount; disconnect on unmount.
  // The singleton is shared with ChatScreen — disconnect here is safe because
  // CameraScreen unmounts before ChatScreen regains focus.
  useEffect(() => {
    let mounted = true;

    mzWs
      .connect({
        onCameraAnalysis: description => {
          if (mounted) {
            setAnalyzing(false);
            setResult(description);
          }
        },
        onError: detail => {
          if (mounted) {
            setAnalyzing(false);
            setWsError(detail);
          }
        },
        onDisconnect: () => {
          if (mounted) {
            setAnalyzing(false);
          }
        },
      })
      .catch(e => {
        if (mounted) {
          setWsError(e instanceof Error ? e.message : 'Connection failed');
        }
      });

    return () => {
      mounted = false;
      mzWs.disconnect();
    };
  }, []);

  const handleCapture = async () => {
    if (!mzWs.isConnected) {
      setWsError('Not connected to server. Please try again.');
      return;
    }

    if (Platform.OS === 'android') {
      const granted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.CAMERA,
      );
      if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
        setWsError('Camera permission denied.');
        return;
      }
    }

    launchCamera({mediaType: 'photo', includeBase64: true, cameraType: 'back', quality: 0.7}, res => {
      if (res.didCancel || !res.assets?.[0]) {return;}
      if (res.errorCode) {
        setWsError(res.errorMessage ?? 'Camera error');
        return;
      }
      const asset = res.assets[0];
      const base64 = asset.base64 ?? '';
      setCapturedUri(asset.uri ?? null);
      setAnalyzing(true);
      setResult(null);
      setWsError(null);
      mzWs.sendCameraFrame(base64);
    });
  };

  return (
    <View style={[styles.container, {backgroundColor: colors.primary}]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Icon name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={[styles.title, {color: colors.text}]}>Live Camera</Text>
        <View style={[styles.liveIndicator, {backgroundColor: colors.danger}]} />
      </View>

      {/* Viewfinder */}
      <View style={[
        styles.viewfinder,
        {borderColor: analyzing ? colors.accent : colors.border},
      ]}>
        <View style={[styles.targetArea, {borderColor: colors.textDim}]}>
          {capturedUri ? (
            <Image
              source={{uri: capturedUri}}
              style={styles.capturedImage}
              resizeMode="cover"
            />
          ) : (
            <>
              <Icon name="camera-outline" size={48} color={colors.textDim} />
              <Text style={[styles.targetText, {color: colors.textDim}]}>Tap capture to take photo</Text>
            </>
          )}

          {/* Corner markers */}
          <View style={[styles.corner, styles.tl, {borderColor: colors.accent}]} />
          <View style={[styles.corner, styles.tr, {borderColor: colors.accent}]} />
          <View style={[styles.corner, styles.bl, {borderColor: colors.accent}]} />
          <View style={[styles.corner, styles.br, {borderColor: colors.accent}]} />
        </View>

        {analyzing && (
          <View style={[styles.analyzingBar, {backgroundColor: colors.primary + 'ee', borderColor: colors.accent + '44'}]}>
            <Icon name="sync-outline" size={18} color={colors.accent} />
            <Text style={[styles.analyzingText, {color: colors.accent}]}>Analyzing frame...</Text>
          </View>
        )}

        {wsError && !analyzing ? (
          <View style={[styles.errorBar, {backgroundColor: colors.primary + 'f0', borderColor: colors.danger + '44'}]}>
            <Icon name="alert-circle-outline" size={16} color={colors.danger} />
            <Text style={[styles.errorText, {color: colors.danger}]} numberOfLines={2}>
              {wsError}
            </Text>
          </View>
        ) : null}

        {result && !analyzing && !wsError ? (
          <View style={[styles.resultBar, {backgroundColor: colors.primary + 'f0', borderColor: colors.accent + '44'}]}>
            <View style={styles.resultHeader}>
              <Icon name="checkmark-circle" size={16} color={colors.accent} />
              <Text style={[styles.resultLabel, {color: colors.accent}]}>AI Analysis</Text>
            </View>
            <Text style={[styles.resultText, {color: colors.text}]}>{result}</Text>
          </View>
        ) : null}
      </View>

      {/* Capture Button */}
      <View style={styles.captureWrap}>
        <TouchableOpacity
          onPress={handleCapture}
          style={[
            styles.captureOuter,
            {borderColor: analyzing ? colors.textDim : colors.accent},
            analyzing && styles.captureDisabled,
          ]}
          activeOpacity={0.8}
          disabled={analyzing}>
          <View style={[styles.captureInner, {backgroundColor: analyzing ? colors.textDim : colors.accent}]} />
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1},
  header: {flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16, paddingTop: 8},
  backBtn: {padding: 4},
  title: {fontSize: 18, fontWeight: '700', flex: 1},
  liveIndicator: {width: 8, height: 8, borderRadius: 4},
  viewfinder: {
    flex: 1,
    margin: 16,
    borderRadius: 20,
    overflow: 'hidden',
    backgroundColor: '#0a0e14',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
  },
  targetArea: {
    width: '80%',
    aspectRatio: 1.5,
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: 'dashed',
    justifyContent: 'center',
    alignItems: 'center',
  },
  targetText: {fontSize: 13, marginTop: 12},
  corner: {position: 'absolute', width: 24, height: 24},
  tl: {top: -2, left: -2, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 4},
  tr: {top: -2, right: -2, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 4},
  bl: {bottom: -2, left: -2, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 4},
  br: {bottom: -2, right: -2, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 4},
  analyzingBar: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderRadius: 12,
    padding: 12,
    paddingHorizontal: 16,
    borderWidth: 1,
  },
  analyzingText: {fontSize: 13, fontWeight: '600'},
  errorBar: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderRadius: 14,
    padding: 14,
    paddingHorizontal: 16,
    borderWidth: 1,
  },
  errorText: {flex: 1, fontSize: 13, lineHeight: 18},
  resultBar: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 20,
    borderRadius: 14,
    padding: 14,
    paddingHorizontal: 16,
    borderWidth: 1,
  },
  resultHeader: {flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8},
  resultLabel: {fontSize: 12, fontWeight: '700'},
  resultText: {fontSize: 13, lineHeight: 20},
  captureWrap: {paddingVertical: 20, alignItems: 'center', paddingBottom: 40},
  captureOuter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 4,
    justifyContent: 'center',
    alignItems: 'center',
  },
  captureDisabled: {opacity: 0.5},
  captureInner: {width: 56, height: 56, borderRadius: 28},
  capturedImage: {width: '100%', height: '100%', borderRadius: 10},
});
