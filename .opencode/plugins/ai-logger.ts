import { spawn } from 'child_process';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';

// Persist user message IDs across events in the process
const MAX_CACHE_SIZE = 1000;
const userMessageIds = new Map<string, string>(); // messageID -> modelID

/**
 * OpenCode AI Logging Plugin
 * Pipes OpenCode agent lifecycle events & prompt submission to scripts/log_hook.py
 */
export const OpenCodeAILoggerPlugin = async (context: any) => {
  process.stderr.write("[ai-logger] Plugin initialized successfully!\n");

  const isWin = os.platform() === 'win32';
  const cwd = process.cwd();
  const launcher = isWin
    ? path.join(cwd, 'scripts', '_pyrun.cmd')
    : 'bash';
  const args = isWin
    ? [path.join(cwd, 'scripts', 'log_hook.py'), '--tool=opencode']
    : [path.join(cwd, 'scripts', '_pyrun.sh'), path.join(cwd, 'scripts', 'log_hook.py'), '--tool=opencode'];

  function sendLog(eventPayload: any) {
    try {
      const child = spawn(launcher, args, { stdio: ['pipe', 'ignore', 'ignore'] });
      child.stdin.write(JSON.stringify(eventPayload));
      child.stdin.end();
    } catch (err: any) {
      writeDebugLog('sendLog.error', { message: err.message });
    }
  }

  function writeDebugLog(hookName: string, data: any) {
    try {
      const logDir = path.join(cwd, '.ai-log');
      if (!fs.existsSync(logDir)) {
        fs.mkdirSync(logDir, { recursive: true });
      }
      const debugFile = path.join(logDir, 'debug.log');
      const logLine = `[${new Date().toISOString()}] hook=${hookName} payload=${JSON.stringify(data)}\n`;
      fs.appendFileSync(debugFile, logLine);
    } catch (e) {
      // Ignore
    }
  }

  return {
    event: async ({ event }: any) => {
      if (!event || !event.properties) return;
      writeDebugLog(`event.${event.type}`, event);

      const props = event.properties;

      // 1. Detect user/assistant message metadata and cache its ID and model name
      if (event.type === 'message.updated' && props.info) {
        if ((props.info.role === 'user' || props.info.role === 'assistant') && props.info.id) {
          // Evict oldest ID if cache limit reached (FIFO)
          if (userMessageIds.size >= MAX_CACHE_SIZE) {
            const oldestId = userMessageIds.keys().next().value;
            if (oldestId !== undefined) {
              userMessageIds.delete(oldestId);
            }
          }
          let modelName = '';
          if (props.info.model) {
            if (typeof props.info.model === 'string') {
              modelName = props.info.model;
            } else if (typeof props.info.model === 'object') {
              modelName = props.info.model.modelID || props.info.model.id || '';
            }
          }
          if (!modelName && props.info.modelID) {
            modelName = props.info.modelID;
          }
          userMessageIds.set(props.info.id, modelName);
        }
      }

      // 2. Detect message part containing prompt text or tool execution results
      if (event.type === 'message.part.updated' && props.part) {
        const part = props.part;
        
        // A. User prompt text submission
        if (part.type === 'text' && part.messageID && userMessageIds.has(part.messageID)) {
          const promptText = part.text || '';
          if (promptText.trim()) {
            const modelName = userMessageIds.get(part.messageID) || '';
            sendLog({
              event: 'UserPromptSubmit',
              source: 'opencode',
              prompt: promptText,
              session_id: props.sessionID || part.sessionID || '',
              model: modelName
            });
            userMessageIds.delete(part.messageID);
          }
        }

        // B. Assistant tool execution finish (completed or failed)
        if (part.type === 'tool' && part.state && (part.state.status === 'completed' || part.state.status === 'failed')) {
          const modelName = part.messageID ? (userMessageIds.get(part.messageID) || '') : '';
          sendLog({
            event: 'ToolUse',
            source: 'opencode',
            session_id: props.sessionID || part.sessionID || '',
            model: modelName,
            tool: part.tool || '',
            tool_input: part.state.input,
            tool_response: part.state.output || part.state.error || ''
          });
        }
      }

      // 3. Handle session idle/end lifecycle
      if (event.type === 'session.idle' || event.type === 'session.end') {
        sendLog({
          event: 'SessionEnd',
          source: 'opencode',
          session_id: props.sessionID || ''
        });
      }
    }
  };
};
