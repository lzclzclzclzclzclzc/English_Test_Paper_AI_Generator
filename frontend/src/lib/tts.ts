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
 * TTS 播放听力原文
 * @param stem 听力原文，格式：M: xxx\nW: xxx\nQuestion: xxx
 */
export async function speakStem(stem: string): Promise<void> {
  // 停止之前的播放
  window.speechSynthesis.cancel();

  const lines = stem.split("\n");
  const utterances: SpeechSynthesisUtterance[] = [];

  // 预获取语音
  const maleVoice = getMaleVoice();
  const femaleVoice = getFemaleVoice();

  for (const line of lines) {
    const speakerMatch = line.match(/^(M|W):\s*(.*)$/);
    if (speakerMatch) {
      const [, speaker, text] = speakerMatch;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      utterance.rate = 0.85;

      // 根据说话者设置不同的 voice
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
      // Question: 或其他内容，用默认 voice
      const utterance = new SpeechSynthesisUtterance(line);
      utterance.lang = "en-US";
      utterance.rate = 0.9;
      utterances.push(utterance);
    }
  }

  // 串行播放所有语句
  for (const utterance of utterances) {
    await new Promise<void>((resolve) => {
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve(); // 出错时继续下一句
      window.speechSynthesis.speak(utterance);
    });
  }
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
