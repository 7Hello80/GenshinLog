new Vue({
    el: '#app',
    data() {
        return {
            gachaUrl: '',
            loading: false,
            gachaData: {
                '301': {
                    name: '角色活动祈愿',
                    pulls: [],
                    stats: {
                        total_pulls: 0,
                        total_primogems: 0,
                        five_star_count: 0,
                        four_star_count: 0
                    }
                },
                '200': {
                    name: '常驻祈愿',
                    pulls: [],
                    stats: {
                        total_pulls: 0,
                        total_primogems: 0,
                        five_star_count: 0,
                        four_star_count: 0
                    }
                },
                '302': {
                    name: '武器活动祈愿',
                    pulls: [],
                    stats: {
                        total_pulls: 0,
                        total_primogems: 0,
                        five_star_count: 0,
                        four_star_count: 0
                    }
                },
                '500': {
                    name: '集录祈愿',
                    pulls: [],
                    stats: {
                        total_pulls: 0,
                        total_primogems: 0,
                        five_star_count: 0,
                        four_star_count: 0
                    }
                }
            },
            displayOrder: ['301', '302', '200', '500'],
            activeTab: '301',
            errorMessage: '',
            progressTimer: null,
            loadingInstance: null,
            taskId: '', // 任务ID，用于区分不同用户的请求
            warning: '<i class="fa-solid fa-info-circle" style="color: #F0E68C;"></i>',
            success: '<i class="fa-solid fa-check-circle" style="color: #00FA9A;"></i>',
            error: '<i class="fa-solid fa-times-circle" style="color: #F08080;"></i>'
        };
    },
    mounted() {
        // 生成唯一任务ID
        this.generateTaskId();
    },
    computed: {
        currentPool() {
            return this.gachaData[this.activeTab] || null;
        },
        reversedFiveStarPulls() {
            return this.currentPool && this.currentPool.pulls ?
                [...this.currentPool.pulls].reverse() :
                [];
        },
        reversedFourStarPulls() {
            return this.currentPool && this.currentPool.four_star_pulls ?
                [...this.currentPool.four_star_pulls].reverse() :
                [];
        },
    },
    methods: {
        generateTaskId() {
            // 生成唯一任务ID
            if (typeof crypto !== 'undefined' && crypto.randomUUID) {
                this.taskId = crypto.randomUUID();
            } else {
                // 兼容旧浏览器，生成伪随机ID
                this.taskId = 'task_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            }
            console.log('任务ID:', this.taskId);
        },
        formatNumber(num) {
            return num.toLocaleString();
        },
        getProgressBarClass(pulls) {
            if (pulls >= 90) return 'red';
            if (pulls >= 73) return 'yellow';
            if (pulls >= 50) return 'orange';
            return 'blue';
        },
        getProgressBarClass4Star(pulls) {
            if (pulls >= 10) return 'red';
            if (pulls >= 9) return 'yellow';
            return 'blue';
        },
        async analyzeGacha() {
            if (!this.gachaUrl.trim()) {
                mdui.snackbar({ message: `${this.warning} <span>请输入抽卡链接</span`, placement: "top" });
                return;
            }

            this.loading = true;
            this.errorMessage = '';

            // 创建loading实例
            this.loadingInstance = this.$loading({
                lock: true,
                text: '加载中...',
                spinner: 'el-icon-loading',
                background: 'rgba(0, 0, 0, 0.7)'
            });

            // 启动定时器，循环获取进度
            this.progressTimer = setInterval(async () => {
                try {
                    const progressResponse = await fetch(`/api/getPage?task_id=${this.taskId}`, {
                        method: 'GET'
                    });
                    const progressData = await progressResponse.json();

                    if (progressData && progressData.name && progressData.page) {
                        // 动态更新loading文本
                        if (this.loadingInstance) {
                            this.loadingInstance.text = `${progressData.name}${progressData.page}`;
                        }
                    }
                } catch (error) {
                    console.error('获取进度失败:', error);
                }
            }, 500);

            try {
                // 请求抽卡数据
                const analyzeResponse = await fetch('/api/gachaLog', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        url: this.gachaUrl,
                        task_id: this.taskId
                    }),
                });

                const analyzeResult = await analyzeResponse.json();

                if (analyzeResult.success && analyzeResult.data) {
                    // 创建新对象替换
                    this.gachaData = JSON.parse(JSON.stringify(analyzeResult.data));

                    mdui.snackbar({ message: `${this.success} <span>分析完成</span`, placement: "top" });
                } else {
                    this.errorMessage = analyzeResult.error || '分析失败，请检查链接是否正确';
                    mdui.snackbar({ message: `${this.error} <span>${this.errorMessage}</span`, placement: "top" });
                }
            } catch (error) {
                this.errorMessage = '网络错误，请稍后重试';
                mdui.snackbar({ message: `${this.error} <span>${this.errorMessage}</span`, placement: "top" });
                console.error('分析错误:', error);
            } finally {
                // 停止定时器
                if (this.progressTimer) {
                    clearInterval(this.progressTimer);
                    this.progressTimer = null;
                }
                // 关闭loading实例
                if (this.loadingInstance) {
                    this.loadingInstance.close();
                    this.loadingInstance = null;
                }
                this.loading = false;
            }
        }
    }
});