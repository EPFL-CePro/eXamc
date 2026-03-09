(function (factory) {
    if (typeof define === 'function' && define.amd) {
        define(['jquery'], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory(require('jquery'));
    } else {
        factory(window.jQuery);
    }
}(function ($) {
    $.extend(true, $.summernote.lang, {
        'en-US': {
            math: {
                dialogTitle: 'Insert Math',
                tooltip: 'Insert Math',
                pluginTitle: 'Insert math',
                ok: 'Insert',
                cancel: 'Cancel'
            }
        }
    });

    $.extend($.summernote.options, {
        math: {
            icon: '<b>&sum;</b>'
        }
    });

    if (!$.summernote.options.math) {
        $.summernote.options.math = { icon: '<b>&sum;</b>' };
    }

    $.extend($.summernote.plugins, {
        math: function (context) {
            var self = this;
            var ui = $.summernote.ui;
            var $editor = context.layoutInfo.editor;
            var options = context.options;
            var lang = options.langInfo;

            self.events = {
                'summernote.keyup summernote.mouseup summernote.change summernote.scroll': function () {
                    self.update();
                },
                'summernote.disable summernote.dialog.shown': function () {
                    self.hide();
                }
            };

            context.memo('button.math', function () {
                var icon =
                    (options.math && options.math.icon) ||
                    ($.summernote.options.math && $.summernote.options.math.icon) ||
                    'Σ';

                var button = ui.button({
                    contents: icon,
                    container: false,
                    tooltip: lang.math.tooltip,
                    click: function () {
                        context.invoke('editor.saveRange');
                        context.invoke('math.show');
                    }
                });

                return button.render();
            });

            self.initialize = function () {
                var $container = options.dialogsInBody ? $(document.body) : $editor;

                var body = `
                    <div class="form-group">
                        <p>
                            Type
                            <a href="https://khan.github.io/KaTeX/function-support.html" target="_blank">
                                LaTeX markup
                            </a>
                            here:
                        </p>
                        <p>
                            <input id="note-latex" class="note-latex form-control" type="text">
                        </p>
                        <p>Preview:</p>
                        <div style="min-height:20px;">
                            <span class="note-math-dialog"></span>
                        </div>
                    </div>
                `;

                self.$dialog = ui.dialog({
                    title: lang.math.dialogTitle,
                    body: body,
                    footer: '<button type="button" class="btn btn-primary note-math-btn">' + lang.math.ok + '</button>'
                }).render().appendTo($container);

                self.$popover = ui.popover({
                    className: 'note-math-popover'
                }).render().appendTo(options.container);

                var $content = self.$popover.find('.popover-content,.note-popover-content');
                context.invoke('buttons.build', $content, ['math']);
            };

            self.destroy = function () {
                ui.hideDialog(self.$dialog);
                self.$dialog.remove();
                self.$popover.remove();
            };

            self.hasMath = function (node) {
                return node && $(node).hasClass('note-math');
            };

            self.isOnMath = function (range) {
                var ancestor = $.summernote.dom.ancestor(range.sc, self.hasMath);
                return !!ancestor && (ancestor === $.summernote.dom.ancestor(range.ec, self.hasMath));
            };

            self.update = function () {
                if (!context.invoke('editor.hasFocus')) {
                    self.hide();
                    return;
                }

                var rng = context.invoke('editor.getLastRange');
                if (rng.isCollapsed() && self.isOnMath(rng)) {
                    var node = $.summernote.dom.ancestor(rng.sc, self.hasMath);
                    var latex = $(node).find('.note-latex');

                    if (latex.text().length !== 0) {
                        self.$popover.find('button').html(latex.text());
                        var pos = $.summernote.dom.posFromPlaceholder(node);
                        self.$popover.css({
                            display: 'block',
                            left: pos.left,
                            top: pos.top
                        });
                    } else {
                        self.hide();
                    }
                } else {
                    self.hide();
                }
            };

            self.hide = function () {
                self.$popover.hide();
            };

            self.bindEnterKey = function ($input, $btn) {
                $input.off('keypress.note-math-enter').on('keypress.note-math-enter', function (event) {
                    if (event.keyCode === 13) {
                        event.preventDefault();
                        $btn.trigger('click');
                    }
                });
            };

            self.bindLabels = function () {
                self.$dialog.find('.form-control:first').focus().select();
                self.$dialog.find('label').on('click', function () {
                    $(this).parent().find('.form-control:first').focus();
                });
            };

            self.bindPreview = function () {
                var $latexInput = self.$dialog.find('#note-latex');
                var $mathPreview = self.$dialog.find('.note-math-dialog');

                function renderMath() {
                    if (!$latexInput.length || !$mathPreview.length) {
                        return;
                    }

                    var tex = $latexInput.val() || '';
                    var previewEl = $mathPreview[0];
                    var oldHtml = previewEl.innerHTML;

                    if (!tex.trim()) {
                        previewEl.innerHTML = '';
                        return;
                    }

                    try {
                        katex.render(tex, previewEl, {
                            throwOnError: true
                        });
                    } catch (e) {
                        previewEl.innerHTML = oldHtml;
                    }
                }

                $latexInput.off('input.note-math keyup.note-math');
                $latexInput.on('input.note-math keyup.note-math', renderMath);

                renderMath();
            };

            self.show = function () {
                var $mathSpan = self.$dialog.find('.note-math-dialog');
                var $latexSpan = self.$dialog.find('#note-latex');
                var $selectedMathNode = self.getSelectedMath();

                if ($selectedMathNode === null) {
                    $mathSpan.empty();
                    $latexSpan.val('');
                } else {
                    var hiddenLatex = $selectedMathNode.find('.note-latex').text();
                    $latexSpan.val(hiddenLatex);

                    if (hiddenLatex.trim()) {
                        try {
                            katex.render(hiddenLatex, $mathSpan[0], {
                                throwOnError: false
                            });
                        } catch (e) {
                            $mathSpan.text(hiddenLatex);
                        }
                    } else {
                        $mathSpan.empty();
                    }
                }

                self.showMathDialog().then(function () {
                    ui.hideDialog(self.$dialog);

                    var latexValue = $latexSpan.val() || '';
                    var $mathNodeClone = $('<span class="note-math"></span>');

                    if (latexValue.trim()) {
                        try {
                            katex.render(latexValue, $mathNodeClone[0], {
                                throwOnError: false
                            });
                        } catch (e) {
                            $mathNodeClone.text(latexValue);
                        }
                    }

                    $('<span>')
                        .addClass('note-latex')
                        .css('display', 'none')
                        .text(latexValue)
                        .appendTo($mathNodeClone);

                    context.invoke('editor.restoreRange');
                    context.invoke('editor.focus');

                    if ($selectedMathNode === null) {
                        if ($.trim(latexValue) !== '') {
                            context.invoke('editor.insertNode', $mathNodeClone[0]);
                        }
                    } else {
                        if ($.trim(latexValue) === '') {
                            $selectedMathNode.remove();
                        } else {
                            $selectedMathNode.replaceWith($mathNodeClone);
                        }
                    }
                });
            };

            self.showMathDialog = function () {
                return $.Deferred(function (deferred) {
                    var $editBtn = self.$dialog.find('.note-math-btn');
                    var $latexInput = self.$dialog.find('#note-latex');

                    ui.onDialogShown(self.$dialog, function () {
                        context.triggerEvent('dialog.shown');
                        self.bindPreview();
                        self.bindEnterKey($latexInput, $editBtn);
                        self.bindLabels();

                        $editBtn.off('click.note-math').on('click.note-math', function (e) {
                            e.preventDefault();
                            deferred.resolve({});
                        });
                    });

                    ui.onDialogHidden(self.$dialog, function () {
                        $editBtn.off('click.note-math');
                        $latexInput.off('input.note-math keyup.note-math keypress.note-math-enter');

                        if (deferred.state() === 'pending') {
                            deferred.reject();
                        }
                    });

                    ui.showDialog(self.$dialog);
                });
            };

            self.getSelectedMath = function () {
                var selection = window.getSelection();
                if (selection) {
                    var $selectedMathNode = null;
                    var $mathNodes = $('.note-math');

                    $mathNodes.each(function () {
                        if (selection.containsNode(this, true)) {
                            $selectedMathNode = $(this);
                            return false;
                        }
                    });

                    return $selectedMathNode;
                }

                return null;
            };
        }
    });
}));