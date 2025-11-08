import React, { useState, useCallback, useRef, useEffect, useReducer } from 'react';
import Draggable from 'react-draggable';
import './FloatingPrompter.css'; // Import the CSS file

// --- Constants ---
const WEBSOCKET_URL = 'ws://localhost:8000';
const PASSIVE_RECONNECT_DELAY_MS = 10000; // 10 seconds for background retry
const INITIAL_OPACITY = 0.6;
const MAX_STATUS_MESSAGES = 10; // Maximum number of status messages to keep

// --- Helper Function ---
const getBackgroundColorWithOpacity = (baseColor, opacity) => {
  // Basic function to apply opacity to an rgba color string base
  // Assumes baseColor is like 'rgba(r, g, b,'
  return `${baseColor} ${opacity})`;
};

// --- Sub-components ---

const PrompterHeader = React.memo(({ opacity, isMinimized, onMinimize, onClose, connectionHealth }) => (
  <div
    className="prompter-header"
    style={{ backgroundColor: getBackgroundColorWithOpacity('rgba(50, 50, 50,', opacity * 0.9) }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span className="drag-handle" aria-label="Drag handle">☰</span>
      <span className="app-title">OpenAI Virtual Teleprompter</span>
      <ConnectionHealthIndicator connectionHealth={connectionHealth} />
    </div>
    <div className="header-controls">
      <button onClick={onMinimize} aria-label={isMinimized ? "Maximize" : "Minimize"}>
        {isMinimized ? '+' : '-'}
      </button>
      <button onClick={onClose} aria-label="Close Prompter" tabIndex="-1">
        X
      </button>
    </div>
  </div>
));

const ConnectionHealthIndicator = React.memo(({ connectionHealth }) => {
  const getHealthColor = () => {
    switch (connectionHealth) {
      case 'connected': return '#10b981'; // green
      case 'connecting': return '#f59e0b'; // yellow
      case 'disconnected': return '#ef4444'; // red
      default: return '#6b7280'; // gray
    }
  };

  const getHealthLabel = () => {
    switch (connectionHealth) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting';
      case 'disconnected': return 'Disconnected';
      default: return 'Unknown';
    }
  };

  return (
    <div
      className={`connection-health-indicator ${connectionHealth}`}
      style={{ backgroundColor: getHealthColor() }}
      aria-label={`Connection status: ${getHealthLabel()}`}
      title={getHealthLabel()}
    />
  );
});

const LoadingSpinner = React.memo(() => (
  <span className="loading-spinner" aria-label="Loading">⟳</span>
));

const StatusMessageLog = React.memo(({ statusMessages, onRetry, isConnecting, connectionHealth }) => {
  // Show retry button if disconnected (not connected and not actively connecting)
  const showRetryButton = connectionHealth === 'disconnected' && !isConnecting;

  // Only show the most recent message to keep UI clean
  const latestMessage = statusMessages.length > 0 ? statusMessages[statusMessages.length - 1] : null;

  if (!latestMessage && !showRetryButton) {
    return null; // Hide completely if no message and no retry button
  }

  return (
    <div className="status-message-log">
      {latestMessage && (
        <div className={`status-message ${latestMessage.type}`}>
          {latestMessage.type === 'connecting' && <LoadingSpinner />}
          <span className="status-text">{latestMessage.message}</span>
        </div>
      )}
      {showRetryButton && (
        <button
          className="retry-button"
          onClick={onRetry}
          disabled={isConnecting}
          aria-label="Retry connection"
        >
          &#8634; Retry Connection
        </button>
      )}
    </div>
  );
});

const ListeningButton = React.memo(({ isListening, isPaused, onClick, opacity, disabled }) => {
  const isDisabled = isPaused || disabled;
  return (
    <button
      className={`prompter-button ${isListening ? 'listening-button-active' : 'listening-button-inactive'} ${isDisabled ? 'disabled' : ''}`}
      onClick={onClick}
      disabled={isDisabled}
      style={{ '--bg-opacity': opacity }} // Pass opacity as CSS variable
      aria-label={isListening ? "Stop Listening" : "Start Listening"}
      title={disabled ? "Connect to backend first" : ""}
    >
      {isListening ? 'Stop Listening' : 'Start Listening'}
    </button>
  );
});

const ResponseDisplay = React.memo(({ displayedResponse, currentResponse, opacity }) => {
  const hasContent = displayedResponse || currentResponse;

  return (
    <div
      className="response-display"
      style={{ backgroundColor: getBackgroundColorWithOpacity('rgba(30, 30, 30,', opacity * 0.7) }}
      aria-live="polite" // Announce changes to screen readers
    >
      {!hasContent ? (
        <div className="response-placeholder">
          <div>Responses will appear here...</div>
          <div style={{ fontSize: '0.9em', marginTop: '8px', opacity: 0.7 }}>
            Press Spacebar to start listening
          </div>
        </div>
      ) : (
        <pre>
          {displayedResponse}
          {currentResponse && (
            <>
              {displayedResponse ? '\n\n' : ''} {/* Add spacing only if there's prior displayed text */}
              <span className="current-response-text">{currentResponse}</span>
            </>
          )}
        </pre>
      )}
    </div>
  );
});

const StatusBar = React.memo(({ apiCallCount, maxApiCalls }) => {
  const displayText = maxApiCalls > 0
    ? `${apiCallCount}/${maxApiCalls}`
    : `${apiCallCount}${maxApiCalls === -1 ? '/∞' : ''}`;

  return (
    <div className="status-bar">
      <p style={{ fontSize: '0.85em', opacity: 0.7 }}>
        API Calls: {displayText}
      </p>
    </div>
  );
});

const AudioLevelMeter = React.memo(({ level, isListening }) => {
  if (!isListening) return null;

  const percentage = Math.min(100, Math.max(0, level));
  const barColor = percentage > 70 ? '#10b981' : percentage > 30 ? '#f59e0b' : '#6b7280';

  return (
    <div className="audio-level-meter">
      <label>Microphone Level:</label>
      <div className="audio-level-bar-container">
        <div
          className="audio-level-bar"
          style={{ width: `${percentage}%`, backgroundColor: barColor }}
        />
      </div>
      <span className="audio-level-text">{percentage}%</span>
    </div>
  );
});

const OpacitySlider = React.memo(({ opacity, onChange }) => (
  <div className="opacity-control">
    <label htmlFor="opacity-slider">Opacity</label>
    <input
      id="opacity-slider" // Associate label with input
      type="range"
      min="0.1"
      max="1"
      step="0.1"
      value={opacity}
      onChange={onChange}
      aria-label="Adjust prompter opacity"
    />
  </div>
));

const ErrorAlert = React.memo(({ error, onClose }) => (
  <div className="error-alert" role="alert">
    {error}
    <button
      className="error-alert-close-button"
      onClick={onClose}
      aria-label="Close error message"
    >
      ✖
    </button>
  </div>
));


// --- Response State Reducer ---
// Handles response streaming with proper state management (no stale closures)
const responseReducer = (state, action) => {
  switch (action.type) {
    case 'ADD_DELTA':
      // Append streaming delta to current response
      return {
        ...state,
        currentResponse: state.currentResponse + (action.payload || '')
      };
    case 'COMPLETE_RESPONSE':
      // Move current response to displayed, clear streaming buffer
      return {
        currentResponse: '',
        displayedResponse: state.displayedResponse + state.currentResponse
      };
    case 'NEW_RESPONSE':
      // Clear both when new response sequence starts
      return {
        currentResponse: '',
        displayedResponse: ''
      };
    case 'CLEAR_ALL':
      // Clear everything
      return {
        currentResponse: '',
        displayedResponse: ''
      };
    default:
      return state;
  }
};

// --- Main Component ---

export default function FloatingPrompter() {
  // Connection state
  const [connectionHealth, setConnectionHealth] = useState('disconnected'); // 'disconnected' | 'connecting' | 'connected'
  const [isConnecting, setIsConnecting] = useState(false);
  const [statusMessages, setStatusMessages] = useState([]); // Array of {timestamp, type, message, icon}

  // Assistant state
  const [apiCallCount, setApiCallCount] = useState(0);
  const [maxApiCalls, setMaxApiCalls] = useState(-1); // -1 = unlimited
  const [isPaused, setIsPaused] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [responseState, dispatchResponse] = useReducer(responseReducer, {
    currentResponse: '',
    displayedResponse: ''
  });
  const [audioLevel, setAudioLevel] = useState(0); // Audio level 0-100

  // UI state
  const [error, setError] = useState('');
  const [isMinimized, setIsMinimized] = useState(false);
  const [opacity, setOpacity] = useState(INITIAL_OPACITY);
  const [showAlert, setShowAlert] = useState(false);

  const ws = useRef(null);
  const passiveReconnectTimeout = useRef(null);
  const containerRef = useRef(null); // Ref for the main draggable container

  // --- Status Message Logging Helper ---
  const addStatusMessage = useCallback((type, message, icon = '') => {
    setStatusMessages(prev => {
      const newMessage = {
        timestamp: Date.now(),
        type, // 'connecting', 'success', 'error', 'info'
        message,
        icon
      };
      const updated = [...prev, newMessage];
      // Keep only the last MAX_STATUS_MESSAGES
      return updated.slice(-MAX_STATUS_MESSAGES);
    });
  }, []);

  // --- WebSocket Message Sending ---
  const sendWebSocketMessage = useCallback((type, payload) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      try {
        ws.current.send(JSON.stringify({ type, ...payload }));
      } catch (err) {
        console.error('Failed to send WebSocket message:', err);
        setError(`Failed to send message: ${err.message}`);
        setShowAlert(true);
      }
    } else {
      console.error('WebSocket is not connected or not ready.');
      setError('WebSocket is not connected. Cannot send message.');
      setShowAlert(true);
      // Optionally attempt to reconnect here if sending fails
      // connectWebSocket();
    }
  }, []); // No dependencies needed as ws.current is a ref

  // --- Response Handling ---
  const handleAssistantResponse = useCallback((responseData) => {
    if (responseData?.type === 'response.audio_transcript.delta') {
      // Append streaming delta
      dispatchResponse({ type: 'ADD_DELTA', payload: responseData.delta });
    } else if (responseData?.type === 'response.complete') {
      // Move current response to displayed, clear streaming buffer
      dispatchResponse({ type: 'COMPLETE_RESPONSE' });
      console.log('Complete response received.');
    }
  }, []); // No stale closure issues with reducer!

  // --- WebSocket Message Receiving ---
  const handleWebSocketMessage = useCallback((event) => {
    try {
      const data = JSON.parse(event.data);
      switch (data?.type) {
        case 'status':
          console.log(`[STATUS] Received: is_listening=${data.is_listening}, is_paused=${data.is_paused}, status="${data.status}"`);
          setIsListening(data.is_listening);
          setIsPaused(data.is_paused);
          console.log(`[STATUS] Updated isListening to: ${data.is_listening}`);
          break;
        case 'transcript': // Assuming transcript might still be used for raw user speech
           // Decide how to display raw transcript if needed, e.g., in a separate area
           // console.log("Transcript:", data.transcript);
           // For now, let's append it to currentResponse for visibility
           // setCurrentResponse(prev => prev + (data.transcript || ''));
          break;
        case 'new_response':
           // Signal that a new response sequence is starting.
           // Clear both displayed and current responses.
           dispatchResponse({ type: 'NEW_RESPONSE' });
           break;
        case 'response': // This wraps the assistant's response chunks
          handleAssistantResponse(data.data);
          break;
        case 'api_call_count':
          setApiCallCount(data.count);
          break;
        case 'config':
          if (data.max_api_calls !== undefined) {
            setMaxApiCalls(data.max_api_calls);
          }
          break;
        case 'audio_level':
          setAudioLevel(data.level);
          break;
        case 'debug':
          // Display debug messages in status area for troubleshooting
          if (data.message) {
            addStatusMessage('debug', data.message);
          }
          break;
        case 'error':
          const errorMsg = data.error?.message || 'An unknown backend error occurred.';
          setError(errorMsg);
          setShowAlert(true);
          console.error('Backend Error:', errorMsg);
          break;
        default:
          console.warn('Unknown message type:', data?.type);
      }
    } catch (parseError) {
      console.error('Failed to parse WebSocket message:', parseError);
      setError('Received malformed data from backend.');
      setShowAlert(true);
    }
  }, [handleAssistantResponse]); // Dependency: handleAssistantResponse

  // --- WebSocket Connection Logic ---
  const connectWebSocket = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      console.log('WebSocket already open.');
      return;
    }
    if (isConnecting) {
      console.log('Connection attempt already in progress.');
      return;
    }

    clearTimeout(passiveReconnectTimeout.current); // Clear any pending passive reconnect
    setIsConnecting(true);
    setConnectionHealth('connecting');
    setError(''); // Clear previous errors
    setShowAlert(false);
    addStatusMessage('connecting', `Connecting to backend... (${WEBSOCKET_URL})`);

    console.log('Attempting to connect WebSocket...');
    ws.current = new WebSocket(WEBSOCKET_URL);

    ws.current.onopen = () => {
      console.log('WebSocket Connected');
      setConnectionHealth('connected');
      setIsConnecting(false);
      addStatusMessage('success', 'Connected to backend successfully');
      addStatusMessage('info', 'Ready to listen - Click "Start Listening" below');

      // Start passive reconnection monitoring (in case connection drops)
      passiveReconnectTimeout.current = setTimeout(() => {
        if (ws.current?.readyState !== WebSocket.OPEN) {
          console.log('Passive reconnect triggered');
          connectWebSocket();
        }
      }, PASSIVE_RECONNECT_DELAY_MS);
    };

    ws.current.onclose = (event) => {
      console.log('WebSocket Disconnected:', event.reason, `Code: ${event.code}`);
      setConnectionHealth('disconnected');
      setIsConnecting(false);

      if (event.code !== 1000) { // 1000 = normal closure
        addStatusMessage('error', 'Connection lost - Start backend server and click Retry');

        // Optional: Uncomment for passive background retry after 30 seconds
        // passiveReconnectTimeout.current = setTimeout(() => {
        //   console.log('Background reconnect attempt');
        //   connectWebSocket();
        // }, PASSIVE_RECONNECT_DELAY_MS * 3); // 30 seconds
      }
    };

    ws.current.onerror = (errorEvent) => {
      console.error('WebSocket Error:', errorEvent);
      setConnectionHealth('disconnected');
      setIsConnecting(false);
      addStatusMessage('error', 'Backend not responding - Start server and click Retry');
    };

    ws.current.onmessage = handleWebSocketMessage;

  }, [isConnecting, handleWebSocketMessage, addStatusMessage]); // Dependencies for connection logic

  // --- Effects ---

  // Initial connection and cleanup
  useEffect(() => {
    connectWebSocket(); // Attempt initial connection on mount

    return () => {
      clearTimeout(passiveReconnectTimeout.current); // Clear timeout on unmount
      if (ws.current) {
        ws.current.close(); // Close WebSocket connection
        console.log('WebSocket connection closed on component unmount.');
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty array - only run on mount/unmount, not when connectWebSocket changes

  // Keyboard listener for Space bar (Start/Stop Listening - Push-to-Talk)
  const toggleListening = useCallback(() => {
    // Toggle between start_listening and stop_listening
    const action = isListening ? 'stop_listening' : 'start_listening';
    console.log(`[SPACEBAR] Current isListening: ${isListening} → Sending action: ${action}`);
    sendWebSocketMessage('control', { action });
  }, [isListening, sendWebSocketMessage]); // Dependencies: isListening, sendWebSocketMessage

  useEffect(() => {
    const handleKeyDown = (event) => {
      // Use event.key for modern browsers, fallback to event.code if needed
      if (event.key === ' ' || event.code === 'Space') {
        // Check if the event target is an input field or similar, to avoid interfering
        const targetTagName = event.target?.tagName?.toLowerCase();
        if (targetTagName !== 'input' && targetTagName !== 'textarea' && targetTagName !== 'select') {
            event.preventDefault(); // Prevent default space bar behavior (e.g., scrolling)
            event.stopPropagation(); // Stop the event from bubbling up
            toggleListening();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [toggleListening]); // Dependency: toggleListening callback

  // --- UI Event Handlers ---
  const handleToggleListening = useCallback(() => {
    // Optimistically update UI? Maybe not best here, wait for status update?
    // Let's send the command and let the status message update the state.
    if (isListening) {
      sendWebSocketMessage('control', { action: 'stop_listening' });
    } else {
      sendWebSocketMessage('control', { action: 'start_listening' });
    }
    // setIsListening(!isListening); // Avoid optimistic update for listening state
  }, [isListening, sendWebSocketMessage]);

  const handleToggleMinimize = useCallback(() => setIsMinimized(prev => !prev), []);
  const handleOpacityChange = useCallback((e) => setOpacity(parseFloat(e.target.value)), []);
  const handleCloseError = useCallback(() => setShowAlert(false), []);
  const handleCloseWindow = useCallback(() => window.close(), []);


  // --- Render ---
  return (
    <Draggable handle=".drag-handle" nodeRef={containerRef}>
      <div
        ref={containerRef}
        className="prompter-container"
        style={{ backgroundColor: getBackgroundColorWithOpacity('rgba(0, 0, 0,', opacity) }}
      >
        <PrompterHeader
          opacity={opacity}
          isMinimized={isMinimized}
          onMinimize={handleToggleMinimize}
          onClose={handleCloseWindow}
          connectionHealth={connectionHealth}
        />

        {/* Show status message log - always visible */}
        <StatusMessageLog
          statusMessages={statusMessages}
          onRetry={connectWebSocket}
          isConnecting={isConnecting}
          connectionHealth={connectionHealth}
        />

        {/* Show main content - always visible but disabled when not connected */}
        {!isMinimized && (
          <div className="prompter-content">
            <ListeningButton
              isListening={isListening}
              isPaused={isPaused}
              onClick={handleToggleListening}
              opacity={opacity}
              disabled={connectionHealth !== 'connected'}
            />
            <AudioLevelMeter level={audioLevel} isListening={isListening} />
            <ResponseDisplay
              displayedResponse={responseState.displayedResponse}
              currentResponse={responseState.currentResponse}
              opacity={opacity}
            />
            <OpacitySlider opacity={opacity} onChange={handleOpacityChange} />
            <StatusBar apiCallCount={apiCallCount} maxApiCalls={maxApiCalls} />
          </div>
        )}

        {showAlert && (
          <ErrorAlert error={error} onClose={handleCloseError} />
        )}
      </div>
    </Draggable>
  );
}
