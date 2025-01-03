document.addEventListener('DOMContentLoaded', function() {
    let activeFilters = {
        keyword: '',
        position: ''
    };

    // Функция для подсчета распределения позиций
    function updatePositionDistribution() {
        const rows = document.querySelectorAll('tbody tr:not(.bg-blue-50)');
        let distribution = {
            top1: 0,
            top3: 0,
            top5: 0,
            top10: 0,
            top100plus: 0
        };

        rows.forEach(row => {
            if (row.style.display !== 'none') {
                // Получаем первую позицию (самая новая дата)
                const cells = Array.from(row.querySelectorAll('td'));
                const firstPositionCell = cells[1]; // Первая ячейка после ключевого слова
                const positionText = firstPositionCell.textContent.trim().split(' ')[0]; // Берем только число, без стрелочки
                const position = parseFloat(positionText);

                if (!isNaN(position)) {
                    if (position >= 1.0 && position < 2.0) distribution.top1++;
                    else if (position >= 1.0 && position < 4.0) distribution.top3++;
                    else if (position >= 1.0 && position < 6.0) distribution.top5++;
                    else if (position >= 1.0 && position < 11.0) distribution.top10++;
                    else if (position >= 100.0) distribution.top100plus++;
                }
            }
        });

        // Обновляем отображение распределения
        document.querySelector('[data-distribution="top1"]').textContent = distribution.top1;
        document.querySelector('[data-distribution="top3"]').textContent = distribution.top3;
        document.querySelector('[data-distribution="top5"]').textContent = distribution.top5;
        document.querySelector('[data-distribution="top10"]').textContent = distribution.top10;
        document.querySelector('[data-distribution="top100plus"]').textContent = distribution.top100plus;
    }

    // Функция фильтрации
    function filterTable() {
        console.log('Активные фильтры:', activeFilters);

        const rows = document.querySelectorAll('tbody tr:not(.bg-blue-50)'); // Исключаем строку со средними значениями

        rows.forEach((row, rowIndex) => {
            let show = true;
            const keyword = row.querySelector('td:first-child').textContent.toLowerCase();
            const cells = Array.from(row.querySelectorAll('td'));
            
            // Получаем значение первой позиции (самая новая дата)
            const firstPositionCell = cells[1]; // Первая ячейка после ключевого слова
            const positionText = firstPositionCell.textContent.trim().split(' ')[0]; // Берем только число, без стрелочки
            const position = parseFloat(positionText);
            
            console.log(`Строка ${rowIndex}:`, {
                keyword,
                position,
                cellsCount: cells.length
            });

            // Фильтр по поиску ключевого слова (частичное совпадение)
            if (activeFilters.keyword && !keyword.includes(activeFilters.keyword.toLowerCase())) {
                show = false;
                console.log(`Строка ${rowIndex}: не прошла фильтр по ключевому слову`);
            }

            // Фильтр по позициям
            if (show && activeFilters.position && !isNaN(position)) {
                let showByPosition = false;
                
                switch (activeFilters.position) {
                    case 'top1':
                        showByPosition = position >= 1.0 && position < 2.0;
                        break;
                    case 'top3':
                        showByPosition = position >= 1.0 && position < 4.0;
                        break;
                    case 'top5':
                        showByPosition = position >= 1.0 && position < 6.0;
                        break;
                    case 'top10':
                        showByPosition = position >= 1.0 && position < 11.0;
                        break;
                    case 'top100plus':
                        showByPosition = position >= 100.0;
                        break;
                    default:
                        showByPosition = true;
                }
                
                console.log(`Строка ${rowIndex}: позиция ${position}, фильтр ${activeFilters.position}, результат: ${showByPosition}`);
                show = showByPosition;
            }

            row.style.display = show ? '' : 'none';
            console.log(`Строка ${rowIndex}: итоговое отображение = ${show}`);
        });

        // Обновляем распределение после фильтрации
        updatePositionDistribution();
    }

    // Обработчик применения фильтров
    document.getElementById('applyFilters').addEventListener('click', function() {
        activeFilters.keyword = document.getElementById('keywordSearch').value;
        activeFilters.position = document.getElementById('positionFilter').value;
        filterTable();
    });

    // Обработчик сброса фильтров
    document.getElementById('resetFilters').addEventListener('click', function() {
        document.getElementById('keywordSearch').value = '';
        document.getElementById('positionFilter').value = '';
        activeFilters.keyword = '';
        activeFilters.position = '';
        filterTable();
    });

    // Инициализация распределения при загрузке страницы
    updatePositionDistribution();

    // Обработчик обновления данных
    document.getElementById('refreshBtn').addEventListener('click', function() {
        const spinner = document.getElementById('refreshSpinner');
        spinner.classList.remove('hidden');
        this.disabled = true;

        fetch(`/project/${projectId}/positions/refresh`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                location.reload();
            } else {
                alert('Ошибка при обновлении данных');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Ошибка при обновлении данных');
        })
        .finally(() => {
            spinner.classList.add('hidden');
            this.disabled = false;
        });
    });

    // Обработчик экспорта в Excel
    document.getElementById('exportBtn').addEventListener('click', function() {
        window.location.href = `/project/${projectId}/positions/export`;
    });
});
