import React, {useState, useEffect} from 'react';
import {View, Text, TouchableOpacity, StyleSheet, Image, PermissionsAndroid, Platform} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import {launchCamera} from 'react-native-image-picker';
import {BRAND} from '../utils/theme';
import {mzWs} from '../api/websocket';

export const CameraScreen: React.FC<{navigation: any}> = ({navigation}) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [wsError, setWsError] = useState<string | null>(null);
  const [capturedUri, setCapturedUri] = useState<string | null>(null);

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

    launchCamera({mediaType: 'photo', includeBase64: true, cameraType: 'back', quality: 0.7}, result => {
      if (result.didCancel || !result.assets?.[0]) return;
      if (result.errorCode) {
        setWsError(result.errorMessage ?? 'Camera error');
        return;
      }
      const asset = result.assets[0];
      const base64 = asset.base64 ?? '';
      setCapturedUri(asset.uri ?? null);
      setAnalyzing(true);
      setResult(null);
      setWsError(null);
      mzWs.sendCameraFrame(base64);
    });
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Icon name="arrow-back" size={22} color={BRAND.text} />
        </TouchableOpacity>
        <Text style={styles.title}>Live Camera</Text>
        <View style={styles.liveIndicator} />
      </View>

      {/* Viewfinder */}
      <View style={[styles.viewfinder, analyzing && styles.viewfinderActive]}>
        <View style={styles.targetArea}>
          {capturedUri ? (
            <Image
              source={{uri: capturedUri}}
              style={styles.capturedImage}
              resizeMode="cover"
            />
          ) : (
            <>
              <Icon name="camera-outline" size={48} color={BRAND.textDim} />
              <Text style={styles.targetText}>Tap capture to take photo</Text>
            </>
          )}

          {/* Corner markers */}
          <View style={[styles.corner, styles.tl]} />
          <View style={[styles.corner, styles.tr]} />
          <View style={[styles.corner, styles.bl]} />
          <View style={[styles.corner, styles.br]} />
        </View>

        {analyzing && (
          <View style={styles.analyzingBar}>
            <Icon name="sync-outline" size={18} color={BRAND.accent} />
            <Text style={styles.analyzingText}>Analyzing frame...</Text>
          </View>
        )}

        {wsError && !analyzing ? (
          <View style={styles.errorBar}>
            <Icon name="alert-circle-outline" size={16} color={BRAND.danger} />
            <Text style={styles.errorText} numberOfLines={2}>
              {wsError}
            </Text>
          </View>
        ) : null}

        {result && !analyzing && !wsError ? (
          <View style={styles.resultBar}>
            <View style={styles.resultHeader}>
              <Icon name="checkmark-circle" size={16} color={BRAND.accent} />
              <Text style={styles.resultLabel}>AI Analysis</Text>
            </View>
            <Text style={styles.resultText}>{result}</Text>
          </View>
        ) : null}
      </View>

      {/* Capture Button */}
      <View style={styles.captureWrap}>
        <TouchableOpacity
          onPress={handleCapture}
          style={[styles.captureOuter, analyzing && styles.captureDisabled]}
          activeOpacity={0.8}
          disabled={analyzing}>
          <View style={styles.captureInner} />
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: BRAND.primary},
  header: {flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16, paddingTop: 8},
  backBtn: {padding: 4},
  title: {color: BRAND.text, fontSize: 18, fontWeight: '700', flex: 1},
  liveIndicator: {width: 8, height: 8, borderRadius: 4, backgroundColor: BRAND.danger},
  viewfinder: {
    flex: 1,
    margin: 16,
    borderRadius: 20,
    overflow: 'hidden',
    backgroundColor: '#0a0e14',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: BRAND.border,
  },
  viewfinderActive: {borderColor: BRAND.accent},
  targetArea: {
    width: '80%',
    aspectRatio: 1.5,
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: BRAND.textDim,
    justifyContent: 'center',
    alignItems: 'center',
  },
  targetText: {color: BRAND.textDim, fontSize: 13, marginTop: 12},
  corner: {position: 'absolute', width: 24, height: 24, borderColor: BRAND.accent},
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
    backgroundColor: BRAND.primary + 'ee',
    borderRadius: 12,
    padding: 12,
    paddingHorizontal: 16,
    borderWidth: 1,
    borderColor: BRAND.accent + '44',
  },
  analyzingText: {color: BRAND.accent, fontSize: 13, fontWeight: '600'},
  errorBar: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: BRAND.primary + 'f0',
    borderRadius: 14,
    padding: 14,
    paddingHorizontal: 16,
    borderWidth: 1,
    borderColor: BRAND.danger + '44',
  },
  errorText: {flex: 1, color: BRAND.danger, fontSize: 13, lineHeight: 18},
  resultBar: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 20,
    backgroundColor: BRAND.primary + 'f0',
    borderRadius: 14,
    padding: 14,
    paddingHorizontal: 16,
    borderWidth: 1,
    borderColor: BRAND.accent + '44',
  },
  resultHeader: {flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8},
  resultLabel: {color: BRAND.accent, fontSize: 12, fontWeight: '700'},
  resultText: {color: BRAND.text, fontSize: 13, lineHeight: 20},
  captureWrap: {paddingVertical: 20, alignItems: 'center', paddingBottom: 40},
  captureOuter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 4,
    borderColor: BRAND.accent,
    justifyContent: 'center',
    alignItems: 'center',
  },
  captureDisabled: {borderColor: BRAND.textDim, opacity: 0.5},
  captureInner: {width: 56, height: 56, borderRadius: 28, backgroundColor: BRAND.accent},
  capturedImage: {width: '100%', height: '100%', borderRadius: 10},
});
