const form = document.getElementById('inputForm');
const searchModeInput = document.getElementById('searchMode');
const searchModeTrigger = document.getElementById('searchModeTrigger');
const searchModeLabel = document.getElementById('searchModeLabel');
const searchModeOptionsContainer = document.getElementById('searchModeOptions');
const customSelect = document.getElementById('customSearchMode');
const queryInput = document.getElementById('queryText');
const queryLabel = document.getElementById('queryLabel');
const refreshWrap = document.getElementById('refreshWrap');
const refreshInput = document.getElementById('refresh');
const resultBody = document.getElementById('resultBody');
const statusEl = document.getElementById('status');
const themeToggle = document.getElementById('themeToggle');
const logoImg = document.getElementById('logoImg');
const exportBtn = document.getElementById('exportBtn');

// Хранение текущих данных для экспорта
let currentTableHeaders = [];
let currentTableRows = [];

function exportToCSV() {
    if (currentTableRows.length === 0) {
        alert('Нет данных для экспорта');
        return;
    }

    // Создаём CSV (добавляем BOM для Excel и используем точку с запятой как разделитель)
    const headers = currentTableHeaders.filter(h => h !== 'Запрос');
    const rows = currentTableRows;
    
    let csv = '\ufeff' + headers.map(h => `"${h.replace(/"/g, '""')}"`).join(';') + '\n';
    
    rows.forEach(row => {
        const values = headers.map(h => {
            const val = row[h] || '';
            return `"${String(val).replace(/"/g, '""')}"`;
        });
        csv += values.join(';') + '\n';
    });

    // Скачивание файла
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', `results_${new Date().getTime()}.csv`);
    link.style.visibility = 'hidden';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function getPreferredTheme() {
    const storedTheme = localStorage.getItem('app-theme');
    if (storedTheme === 'light' || storedTheme === 'dark') {
        return storedTheme;
    }
    return 'dark';
}

function applyTheme(theme) {
    document.body.setAttribute('data-theme', theme);
    document.body.classList.toggle('theme-dark', theme === 'dark');
    localStorage.setItem('app-theme', theme);
    if (logoImg) {
        logoImg.src = theme === 'dark'
            ? '/static/src/logo_black.png'
            : '/static/src/logo_white.png';
    }
    if (themeToggle) {
        if (theme === 'dark') {
            themeToggle.querySelector('.dark-icon').style.display = 'none';
            themeToggle.querySelector('.light-icon').style.display = 'block';
            themeToggle.setAttribute('aria-label', 'Светлая тема');
        } else {
            themeToggle.querySelector('.dark-icon').style.display = 'block';
            themeToggle.querySelector('.light-icon').style.display = 'none';
            themeToggle.setAttribute('aria-label', 'Тёмная тема');
        }
    }
}

function runThemeTransition(nextTheme) {
    if (document.startViewTransition) {
        if (document.documentElement.classList.contains('theme-transitioning')) {
            return;
        }

        document.documentElement.classList.add('theme-transitioning');

        let transition;
        try {
            transition = document.startViewTransition(() => {
                applyTheme(nextTheme);
            });
        } catch (error) {
            applyTheme(nextTheme);
            document.documentElement.classList.remove('theme-transitioning');
            return;
        }

        transition.finished.finally(() => {
            document.documentElement.classList.remove('theme-transitioning');
        });
        return;
    }

    applyTheme(nextTheme);
}

function safe(value) {
    if (value === null || value === undefined || value === "") {
        return "-";
    }
    return String(value);
}

function detectLang(text) {
    if (text === "-") {
        return "ru";
    }
    return /[А-Яа-яЁё]/.test(text) ? "ru" : "en";
}

function wrapCell(value, options = {}) {
    const text = safe(value);
    const lang = detectLang(text);
    const extraClass = options.noHyphen ? " noHyphen" : "";
    return `<span class="cellText${extraClass}" lang="${lang}">${text}</span>`;
}

function wrapAuthors(value) {
    const text = safe(value);
    const lang = detectLang(text);
    const withBreaks = text.replace(/([,;])\s+/g, "$1<wbr> ");
    return `<span class="cellText noHyphen" lang="${lang}">${withBreaks}</span>`;
}

function setStatus(text, isError = false) {
    statusEl.textContent = text;
    statusEl.classList.toggle('error', isError);
}

function formatWhiteList(value) {
    if (value === null || value === undefined) {
        return "-";
    }
    return value ? "Да" : "Нет";
}

function formatQuartile(ranking) {
    const quartile = safe(ranking?.quartile);
    if (!ranking || !ranking.is_fallback_year) {
        return quartile;
    }
    return `${quartile}*`;
}

function renderTitleResult(data) {
    const items = Array.isArray(data) ? data : [data];
    if (!items.length) {
        resultBody.innerHTML = '<tr><td colspan="11" class="muted">Совпадения не найдены.</td></tr>';
        exportBtn.style.display = 'none';
        return;
    }

    currentTableHeaders = ['Авторы', 'Название в Scopus', 'ISSN / eISSN', 'Год', 'Журнал', 'Квартиль', 'SJR', 'Страна', 'Белый список', 'Категория ВАК'];
    currentTableRows = items.map((item) => {
        const scopus = item.scopus || {};
        const ranking = item.ranking || {};
        const authors = Array.isArray(scopus.authors) && scopus.authors.length > 0
            ? scopus.authors.join('; ')
            : '-';

        return {
            'Авторы': authors,
            'Название в Scopus': safe(scopus.title),
            'ISSN / eISSN': `${safe(scopus.issn)} / ${safe(scopus.eissn)}`,
            'Год': safe(scopus.publication_year),
            'Журнал': safe(scopus.journal_name),
            'Квартиль': formatQuartile(ranking),
            'SJR': safe(ranking.sjr),
            'Страна': safe(ranking.country),
            'Белый список': formatWhiteList(ranking.is_white_list),
            'Категория ВАК': safe(ranking.vak_category)
        };
    });

    exportBtn.style.display = 'block';

    resultBody.innerHTML = items.map((item) => {
        const scopus = item.scopus || {};
        const ranking = item.ranking || {};
        const authors = Array.isArray(scopus.authors) && scopus.authors.length > 0
            ? scopus.authors.join('; ')
            : '-';

        return `
    <tr>
            <td>${wrapCell(item.query_title)}</td>
              <td>${wrapAuthors(authors)}</td>
            <td>${wrapCell(scopus.title)}</td>
            <td>${wrapCell(`${safe(scopus.issn)} / ${safe(scopus.eissn)}`)}</td>
            <td>${wrapCell(scopus.publication_year)}</td>
            <td>${wrapCell(scopus.journal_name)}</td>
            <td>${wrapCell(formatQuartile(ranking))}</td>
            <td>${wrapCell(ranking.sjr)}</td>
            <td>${wrapCell(ranking.country)}</td>
            <td>${wrapCell(formatWhiteList(ranking.is_white_list))}</td>
            <td>${wrapCell(ranking.vak_category)}</td>
        </tr>
      `;
    }).join('');
}

function renderAuthorResult(data) {
    const articles = Array.isArray(data.articles) ? data.articles : [];

    if (!articles.length) {
        resultBody.innerHTML = '<tr><td colspan="11" class="muted">Статьи по автору не найдены.</td></tr>';
        exportBtn.style.display = 'none';
        return;
    }

    currentTableHeaders = ['Авторы', 'Название в Scopus', 'ISSN / eISSN', 'Год', 'Журнал', 'Квартиль', 'SJR', 'Страна', 'Белый список', 'Категория ВАК'];
    currentTableRows = articles.map((article) => {
        const ranking = article.ranking || {};
        let authorsStr = Array.isArray(article.authors) && article.authors.length > 0
            ? article.authors.join('; ')
            : safe(article.authors);
        if (!authorsStr || authorsStr === "-") {
            authorsStr = data.query_author;
        }
        return {
            'Авторы': authorsStr,
            'Название в Scopus': safe(article.title),
            'ISSN / eISSN': `${safe(article.issn)} / ${safe(article.eissn)}`,
            'Год': safe(article.publication_year),
            'Журнал': safe(article.journal_name),
            'Квартиль': formatQuartile(ranking),
            'SJR': safe(ranking.sjr),
            'Страна': safe(ranking.country),
            'Белый список': formatWhiteList(ranking.is_white_list),
            'Категория ВАК': safe(ranking.vak_category)
        };
    });
    
    exportBtn.style.display = 'block';

    resultBody.innerHTML = articles.map((article) => {
        const ranking = article.ranking || {};
        let authorsStr = Array.isArray(article.authors) && article.authors.length > 0
            ? article.authors.join('; ')
            : safe(article.authors);
        if (!authorsStr || authorsStr === "-") {
            authorsStr = data.query_author;
        }
        return `
            <tr>
                <td>${wrapCell(data.query_author)}</td>
                <td>${wrapAuthors(authorsStr)}</td>
                <td>${wrapCell(article.title)}</td>
                <td>${wrapCell(`${safe(article.issn)} / ${safe(article.eissn)}`)}</td>
                <td>${wrapCell(article.publication_year)}</td>
                <td>${wrapCell(article.journal_name)}</td>
                <td>${wrapCell(formatQuartile(ranking))}</td>
                <td>${wrapCell(ranking.sjr)}</td>
                <td>${wrapCell(ranking.country)}</td>
                <td>${wrapCell(formatWhiteList(ranking.is_white_list))}</td>
                <td>${wrapCell(ranking.vak_category)}</td>
            </tr>
        `;
    }).join('');
}

function updateModeUI() {
    const mode = searchModeInput.value;
    const isAuthorMode = mode === 'author';

    queryLabel.textContent = isAuthorMode ? 'Введите имя автора' : 'Введите название';
    queryInput.placeholder = isAuthorMode ? 'Иванов или Иванов, И.И.' : 'Название статьи';
    refreshWrap.classList.toggle('hidden', !isAuthorMode);
}

// Custom Select Logic
searchModeTrigger.addEventListener('click', (e) => {
    e.stopPropagation();
    customSelect.classList.toggle('open');
});

document.addEventListener('click', () => {
    if (customSelect.classList.contains('open')) {
        customSelect.classList.remove('open');
    }
});

const options = searchModeOptionsContainer.querySelectorAll('.selectOption');
options.forEach(option => {
    option.addEventListener('click', () => {
        options.forEach(opt => opt.classList.remove('selected'));
        option.classList.add('selected');
        
        const value = option.getAttribute('data-value');
        const text = option.textContent;
        
        searchModeLabel.textContent = text;
        searchModeInput.value = value;
        customSelect.classList.remove('open');
        
        updateModeUI();
    });
});

updateModeUI();

applyTheme(getPreferredTheme());
if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        const current = document.body.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        runThemeTransition(next);
    });
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const mode = searchModeInput.value;
    const query = queryInput.value.trim();

    if (!query) {
        setStatus(mode === 'author' ? 'Введите имя автора' : 'Введите название статьи', true);
        return;
    }

    setStatus('Поиск...');
    resultBody.innerHTML = '<tr><td colspan="11" class="muted">Получаем данные с сервера...</td></tr>';

    try {
        let url;
        if (mode === 'author') {
            const refresh = refreshInput.checked;
            url = `/search/author?author=${encodeURIComponent(query)}&refresh=${refresh}`;
        } else {
            url = `/verify?title=${encodeURIComponent(query)}`;
        }

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.status}`);
        }

        const data = await response.json();

        if (data.detail) {
            throw new Error(String(data.detail));
        }

        if (mode === 'author') {
            if (data.scopus_error) {
                setStatus(`Ошибка Scopus: ${data.scopus_error}`, true);
            } else {
                const cacheMark = data.from_cache ? ' (из кеша)' : '';
                setStatus(`Найдено ${safe(data.returned)} из ${safe(data.total_found)}${cacheMark}`);
            }
            renderAuthorResult(data);
            return;
        }

        const titleItems = Array.isArray(data) ? data : [data];
        const titleError = titleItems.find(item => item && item.scopus_error)?.scopus_error;
        if (titleError) {
            setStatus(`Ошибка Scopus: ${titleError}`, true);
        } else {
            setStatus('Поиск завершён');
        }
        renderTitleResult(titleItems);
    } catch (error) {
        setStatus(`Ошибка: ${error.message}`, true);
        resultBody.innerHTML = '<tr><td colspan="11" class="muted">Произошла ошибка при получении данных.</td></tr>';
        exportBtn.style.display = 'none';
    }
});

// Обработчик кнопки экспорта
if (exportBtn) {
    exportBtn.addEventListener('click', exportToCSV);
}