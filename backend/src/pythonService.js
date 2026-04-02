import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const backendRoot = path.resolve(__dirname, "..");
const projectRoot = path.resolve(__dirname, "..", "..");
const bridgePath = path.join(backendRoot, "api_bridge.py");

const isWindows = process.platform === "win32";
const defaultPython = isWindows
  ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
  : "python3";

const pythonExecutable = process.env.PYTHON_EXECUTABLE || defaultPython;

export function runPythonBridge(command, args = []) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonExecutable, [bridgePath, command, ...args], {
      cwd: projectRoot,
      windowsHide: true,
      env: process.env,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });

    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });

    child.on("error", (error) => {
      reject(new Error(`Failed to execute python process: ${error.message}`));
    });

    child.on("close", (code) => {
      if (code !== 0) {
        reject(
          new Error(
            `Python bridge failed with exit code ${code}. ${stderr.trim() || "No stderr output."}`
          )
        );
        return;
      }

      try {
        const parsed = JSON.parse(stdout.trim() || "{}");
        resolve(parsed);
      } catch (error) {
        reject(
          new Error(
            `Invalid JSON from Python bridge. ${error.message}. Raw output: ${stdout.trim()}`
          )
        );
      }
    });
  });
}
