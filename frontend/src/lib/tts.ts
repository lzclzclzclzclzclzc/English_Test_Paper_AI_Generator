/**
 * 获取可用的英语语音列表
 */
function getEnglishVoices(): SpeechSynthesisVoice[] {
  return window.speechSynthesis.getVoices().filter((v) => v.lang.startsWith("en"));
}

/**
 * 获取男声（优先系统语音，其次网络语音）
 */
function getMaleVoice(): SpeechSynthesisVoice | undefined {
  const voices = getEnglishVoices();
  if (voices.length === 0) return undefined;

  // 优先选择系统语音（更快更可靠）
  const systemVoices = voices.filter((v) => v.localService);

  // 尝试匹配常见男声名称
  const maleNames = [
    "Male", "male", "Brian", "Alex", "Daniel", "George", "Michael",
    "Tom", "Steven", "Ryan", "Paul", "Peter", "John", "Jack", "James",
    "David", "Mark", "Chris", "Robert", "William", "Richard", "Joseph",
    "Donald", "Michael", "Charles", "Thomas", "Gary", "Kevin", "Edward",
    "Jason", "Jeff", "Frank", "Scott", "Eric", "Sam", "Adam", "Ben",
    "Carl", "Doug", "Greg", "Hank", "Ian", "Larry", "Matt", "Mike",
    "Nick", "Ray", "Steve", "Todd", "Walt", "Bruce", "Derek", "Evan",
    "Fred", "Gordon", "Harry", "Jake", "Ken", "Lloyd", "Marvin", "Neil",
    "Oscar", "Pat", "Quinn", "Ralph", "Seth", "Tyler", "Vince", "Will",
    "Google US English Male", "Microsoft David", "Microsoft George", "Microsoft Mark",
  ];

  // 在系统语音中查找
  for (const name of maleNames) {
    const voice = systemVoices.find((v) => v.name.includes(name));
    if (voice) return voice;
  }

  // 在所有语音中查找
  for (const name of maleNames) {
    const voice = voices.find((v) => v.name.includes(name));
    if (voice) return voice;
  }

  // 回退：选择第一个英语语音作为男声
  return systemVoices[0] || voices[0];
}

/**
 * 获取女声（优先系统语音，其次网络语音）
 */
function getFemaleVoice(): SpeechSynthesisVoice | undefined {
  const voices = getEnglishVoices();
  if (voices.length === 0) return undefined;

  // 优先选择系统语音
  const systemVoices = voices.filter((v) => v.localService);

  // 尝试匹配常见女声名称
  const femaleNames = [
    "Female", "female", "Samantha", "Alexa", "Victoria", "Zoe", "Emma",
    "Kate", "Mary", "Anna", "Lisa", "Sarah", "Jennifer", "Michelle",
    "Jessica", "Amanda", "Melissa", "Lauren", "Rachel", "Heather", "Ashley",
    "Kimberly", "Nicole", "Emily", "Megan", "Brittany", "Stephanie", "Elizabeth",
    "Jennifer", "Marie", "Christina", "Lauren", "Lisa", "Michelle", "Sarah",
    "Jessica", "Amanda", "Melissa", "Rachel", "Heather", "Ashley", "Kimberly",
    "Nicole", "Emily", "Megan", "Brittany", "Stephanie", "Elizabeth", "Rebecca",
    "Laura", "Tiffany", "Jessica", "Alex", "Danielle", "Vanessa", "Stacy",
    "Jenna", "Courtney", "Christine", "Molly", "Rachel", "Katherine", "Lindsay",
    "Google US English Female", "Microsoft Zira", "Microsoft Samantha", "Microsoft Emma",
    "Microsoft Eva", "Microsoft Hazel", "Microsoft Clara", "Microsoft Susan",
    "Siri", "Cortana", "Google Assistant",
  ];

  // 在系统语音中查找
  for (const name of femaleNames) {
    const voice = systemVoices.find((v) => v.name.includes(name));
    if (voice) return voice;
  }

  // 在所有语音中查找
  for (const name of femaleNames) {
    const voice = voices.find((v) => v.name.includes(name));
    if (voice) return voice;
  }

  // 回退：选择第一个英语语音作为女声
  return systemVoices[0] || voices[0];
}

/**
 * 全局播放锁：同一时间只允许一段听力播放
 * 通过 useSyncExternalStore 让所有听力组件订阅播放状态
 */
let _playing = false;
let _cancelToken = 0;
const _listeners = new Set<() => void>();

export function isGloballyPlaying(): boolean {
  return _playing;
}

export function subscribePlayingState(callback: () => void): () => void {
  _listeners.add(callback);
  return () => { _listeners.delete(callback); };
}

function _setPlaying(v: boolean): void {
  _playing = v;
  _listeners.forEach((fn) => fn());
}

/**
 * TTS 播放听力原文
 * 如果已有播放进行中，直接返回不播放。
 * @returns true=已开始播放，false=被阻止（已有播放中）
 */
export async function speakStem(stem: string): Promise<boolean> {
  if (_playing) return false;
  _setPlaying(true);
  const myToken = ++_cancelToken;

  try {
    window.speechSynthesis.cancel();

    const lines = stem.split("\n");
    const utterances: SpeechSynthesisUtterance[] = [];

    const maleVoice = getMaleVoice();
    const femaleVoice = getFemaleVoice();

    for (const line of lines) {
      const speakerMatch = line.match(/^(M|W):\s*(.*)$/);
      if (speakerMatch) {
        const [, speaker, text] = speakerMatch;
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "en-US";
        utterance.rate = 0.85;

        if (speaker === "M") {
          if (maleVoice) {
            utterance.voice = maleVoice;
          }
        } else {
          if (femaleVoice) {
            utterance.voice = femaleVoice;
          }
        }

        utterances.push(utterance);
      } else {
        const utterance = new SpeechSynthesisUtterance(line);
        utterance.lang = "en-US";
        utterance.rate = 0.9;
        utterances.push(utterance);
      }
    }

    for (const utterance of utterances) {
      // 被取消（stopAll 调用后 token 变化），立即退出循环
      if (myToken !== _cancelToken) break;
      await new Promise<void>((resolve) => {
        utterance.onend = () => resolve();
        utterance.onerror = () => resolve();
        window.speechSynthesis.speak(utterance);
      });
    }
  } finally {
    // 只有未被外部取消时才重置 playing 状态
    if (myToken === _cancelToken) {
      _setPlaying(false);
    }
  }
  return true;
}

/**
 * 停止所有播放并重置全局锁
 * 通过递增 _cancelToken 使正在运行的 speakStem 循环中断，
 * 不再播放后续语句。
 */
export function stopAll(): void {
  _cancelToken++;
  window.speechSynthesis.cancel();
  _setPlaying(false);
}

/**
 * 预加载 voices（解决某些浏览器首次调用时 voices 列表为空的问题）
 */
export function preloadVoices(): void {
  const loadVoices = () => {
    window.speechSynthesis.getVoices();
  };
  window.speechSynthesis.onvoiceschanged = loadVoices;
  loadVoices();
}
