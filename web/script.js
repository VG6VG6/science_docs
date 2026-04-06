const form = document.getElementById('inputForm');
const titleInput = document.getElementById('title');
const resultBody = document.getElementById('resultBody');
const statusEl = document.getElementById('status');

function safe(value) {
    if (value === null || value === undefined || value === "") {
        return "-";
    }
    return String(value);
}

function setStatus(text, isError = false) {
    statusEl.textContent = text;
    statusEl.style.color = isError ? "#b91c1c" : "#334155";
}

function renderRow(data) {
    const scopus = data.scopus || {};
    const ranking = data.ranking || {};

    resultBody.innerHTML = `
    <tr>
          <td>${safe(data.query_title)}</td>
          <td>${safe(scopus.title)}</td>
          <td>${safe(scopus.issn)} / ${safe(scopus.eissn)}</td>
          <td>${safe(scopus.publication_year)}</td>
          <td>${safe(scopus.journal_name)}</td>
          <td>${safe(ranking.quartile)}</td>
          <td>${safe(ranking.sjr)}</td>
          <td>${safe(ranking.h_index)}</td>
          <td>${safe(ranking.country)}</td>
          <td>${ranking.is_white_list === null || ranking.is_white_list === undefined ? "-" : (ranking.is_white_list ? "Yes" : "No")}</td>
          <td>${safe(ranking.vak_category)}</td>
        </tr>
      `;
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const title = titleInput.value.trim();
    if (!title) {
        setStatus('Please enter a title', true);
        return;
    }

    setStatus('Searching...');
    resultBody.innerHTML = '<tr><td colspan="11" class="muted">Получаем данные с сервера...</td></tr>';

    try {
        const url = `/verify?title=${encodeURIComponent(title)}`;
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        if (data.scopus_error) {
            setStatus(`Scopus error: ${data.scopus_error}`, true);
        } else {
            setStatus('Search completed');
        }
        renderRow(data);
    } catch (error) {
        setStatus(`Error: ${error.message}`, true);
        resultBody.innerHTML = '<tr><td colspan="11" class="muted">An error occurred while fetching data.</td></tr>';
    }
});