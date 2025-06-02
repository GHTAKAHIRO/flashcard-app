console.log("🚀 main.js が Render 上で動いています！");

document.addEventListener('DOMContentLoaded', function () {
    if (typeof rawCards === "undefined") {
        console.error("❌ rawCards が定義されていません！");
        return;
    }

    document.getElementById('flashcard').addEventListener('click', toggleAnswer);
    document.getElementById('knownBtn').addEventListener('click', markKnown);
    document.getElementById('unknownBtn').addEventListener('click', markUnknown);

    isPracticeMode = typeof mode !== 'undefined' && mode === 'practice';
    initCards(rawCards);
});

let cards = [];
let currentIndex = 0;
let showingAnswer = false;
let cardStatus = {};  // id => 'known' or 'unknown'
let isPracticeMode = false;

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

function initCards(data) {
    cards = shuffle(data.slice());
    currentIndex = 0;
    showingAnswer = false;
    cardStatus = {};
    renderCard();
}

function renderCard() {
    const card = cards[currentIndex];
    const cardDiv = document.getElementById('flashcard');
    cardDiv.innerHTML = '';

    const questionDiv = document.createElement('div');
    if (card.image_problem) {
        const img = document.createElement('img');
        img.src = card.image_problem;
        questionDiv.appendChild(img);
    }
    if (card.problem_number && card.topic) {
        const text = document.createElement('p');
        text.textContent = `${card.problem_number}: ${card.topic}`;
        questionDiv.appendChild(text);
    }

    cardDiv.appendChild(questionDiv);

    if (showingAnswer && card.image_answer) {
        const answerDiv = document.createElement('div');
        const img = document.createElement('img');
        img.src = card.image_answer;
        answerDiv.appendChild(img);
        cardDiv.appendChild(answerDiv);
    }
}

function toggleAnswer() {
    showingAnswer = !showingAnswer;
    renderCard();
}

function markKnown() {
    const id = cards[currentIndex].id;
    cardStatus[id] = 'known';
    sendResult(id, 'known');
}

function markUnknown() {
    const id = cards[currentIndex].id;
    cardStatus[id] = 'unknown';
    sendResult(id, 'unknown');
}

// 🔥 修正：sendResult関数を拡張
async function sendResult(cardId, result) {
    try {
        console.log('[SUBMIT] 回答送信開始:', cardId, result);
        
        const response = await fetch('/log_result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                card_id: cardId,
                result: result,
                stage: stage,
                mode: mode
            })
        });

        const data = await response.json();
        console.log('[SUBMIT] レスポンス受信:', data);

        if (data.status === 'ok') {
            // 🔥 即時練習判定の処理
            if (data.needs_immediate_practice) {
                console.log('[SUBMIT] 即時練習が必要:', data.completed_chunk);
                // チャンク完了 + 練習が必要
                showChunkCompletionModal(data.completed_chunk, data.message, true);
                return; // ここで処理終了
            } 
            
            if (data.chunk_perfect) {
                console.log('[SUBMIT] チャンク完了（全問正解）:', data.completed_chunk);
                // チャンク完了 + 全問正解
                showChunkCompletionModal(data.completed_chunk, data.message, false);
                return; // ここで処理終了
            }
            
            if (data.practice_complete) {
                console.log('[SUBMIT] 練習完了:', data.completed_chunk);
                // 練習完了
                showPracticeCompleteModal(data.completed_chunk, data.message);
                return; // ここで処理終了
            }
            
            // 通常の次の問題へ
            console.log('[SUBMIT] 通常の次問題へ');
            nextCard();
            
        } else {
            throw new Error(data.message || '回答の送信に失敗しました');
        }

    } catch (error) {
        console.error('[SUBMIT] エラー:', error);
        console.error("❌ サーバーへの記録に失敗しました");
        nextCard(); // エラーでも次に進む
    }
}

// 🔥 チャンク完了モーダル表示
function showChunkCompletionModal(chunkNumber, message, needsPractice) {
    console.log('[MODAL] チャンク完了モーダル表示:', chunkNumber, needsPractice);
    
    // 既存のモーダルがあれば削除
    const existingModal = document.getElementById('chunkCompletionModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'chunkCompletionModal';
    modal.setAttribute('data-bs-backdrop', 'static'); // 背景クリックで閉じない
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header bg-success text-white">
                    <h5 class="modal-title">🎉 チャンク${chunkNumber}完了！</h5>
                </div>
                <div class="modal-body text-center">
                    <p class="mb-3">${message}</p>
                    ${needsPractice ? 
                        '<p class="text-info"><strong>×だった問題を練習してから次のチャンクに進みましょう。</strong></p>' : 
                        '<p class="text-success"><strong>全問正解でした！次のチャンクに進みます。</strong></p>'
                    }
                </div>
                <div class="modal-footer justify-content-center">
                    ${needsPractice ? 
                        `<button type="button" class="btn btn-primary btn-lg me-2" onclick="startChunkPractice(${chunkNumber})">
                            <i class="fas fa-play"></i> 練習開始
                         </button>
                         <button type="button" class="btn btn-outline-secondary" onclick="skipPractice()">
                            <i class="fas fa-forward"></i> スキップ
                         </button>` :
                        `<button type="button" class="btn btn-success btn-lg" onclick="continueToNextChunk()">
                            <i class="fas fa-arrow-right"></i> 次のチャンクへ
                         </button>`
                    }
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Bootstrap modalとして表示
    if (typeof bootstrap !== 'undefined') {
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
        
        // モーダルが閉じられたら削除
        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });
    } else {
        // Bootstrap がない場合はalertで代替
        if (needsPractice) {
            if (confirm(`${message}\n練習を開始しますか？`)) {
                startChunkPractice(chunkNumber);
            } else {
                skipPractice();
            }
        } else {
            alert(message);
            continueToNextChunk();
        }
    }
}

// 🔥 練習完了モーダル表示
function showPracticeCompleteModal(chunkNumber, message) {
    console.log('[MODAL] 練習完了モーダル表示:', chunkNumber);
    
    if (typeof bootstrap !== 'undefined') {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'practiceCompleteModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header bg-info text-white">
                        <h5 class="modal-title">✅ 練習完了！</h5>
                    </div>
                    <div class="modal-body text-center">
                        <p class="mb-3">${message}</p>
                        <p class="text-success">次のチャンクに進みます。</p>
                    </div>
                    <div class="modal-footer justify-content-center">
                        <button type="button" class="btn btn-success btn-lg" onclick="continueToNextChunk()">
                            <i class="fas fa-arrow-right"></i> 次のチャンクへ
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
        
        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });
    } else {
        alert(message);
        continueToNextChunk();
    }
}

// 🔥 練習開始
function startChunkPractice(chunkNumber) {
    console.log('[PRACTICE] 練習開始:', chunkNumber);
    
    const modal = document.getElementById('chunkCompletionModal');
    if (modal) {
        modal.remove();
    }
    
    // 練習開始のURLにリダイレクト
    const currentSource = getCurrentSource();
    console.log('[PRACTICE] リダイレクト先:', `/start_chunk_practice/${currentSource}/${chunkNumber}`);
    window.location.href = `/start_chunk_practice/${currentSource}/${chunkNumber}`;
}

// 🔥 練習スキップ
function skipPractice() {
    console.log('[PRACTICE] 練習スキップ');
    
    const modal = document.getElementById('chunkCompletionModal');
    if (modal) {
        modal.remove();
    }
    
    const currentSource = getCurrentSource();
    window.location.href = `/skip_chunk_practice/${currentSource}`;
}

// 🔥 次のチャンクへ
function continueToNextChunk() {
    console.log('[CHUNK] 次のチャンクへ');
    
    // モーダルを閉じる
    const completionModal = document.getElementById('chunkCompletionModal');
    const practiceModal = document.getElementById('practiceCompleteModal');
    
    if (completionModal) completionModal.remove();
    if (practiceModal) practiceModal.remove();
    
    // ページをリロードして次のチャンクへ
    window.location.reload();
}

// 🔥 現在のソース名を取得
function getCurrentSource() {
    // URLから教材名を取得 (例: /study/JOYFUL → JOYFUL)
    const pathParts = window.location.pathname.split('/');
    const source = pathParts[pathParts.length - 1];
    console.log('[SOURCE] 現在の教材:', source);
    return source;
}

// 🔥 既存のnextCard関数はそのまま維持
function nextCard() {
    currentIndex++;

    if (currentIndex >= cards.length) {
        if (isPracticeMode) {
            const wrongCards = cards.filter(card => cardStatus[card.id] === 'unknown');
            if (wrongCards.length > 0) {
                alert("✏️ 間違えたカードがあります。設定画面から再度練習してください。");
            } else {
                alert("✅ 練習完了！すべて正解です！");
            }
            window.location.href = `/prepare/${cards[0].source}`;
            return;
        } else {
            alert("✅ テスト完了！");
            window.location.href = `/prepare/${cards[0].source}`;
            return;
        }
    }

    showingAnswer = false;
    renderCard();
}