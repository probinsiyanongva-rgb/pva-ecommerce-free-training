/* PVA Free Training -- E-commerce VA Foundations
   Small, dependency-free activity engine. Each render function takes
   a container element, a data object, and an onComplete callback that
   fires once the learner has satisfied the activity. */

(function(){

  function el(tag, cls, text){
    var e = document.createElement(tag);
    if(cls) e.className = cls;
    if(text !== undefined) e.textContent = text;
    return e;
  }

  /* ---------------- QUIZ ---------------- */
  function renderQuiz(container, data, onComplete){
    container.innerHTML = "";
    var wrap = el("div", "activity");
    var solvedCount = 0;

    data.questions.forEach(function(q, qi){
      var item = el("div", "activity-item");
      var p = el("p", "q", q.q);
      item.appendChild(p);
      var list = el("div", "opt-list");
      var feedback = el("div", "feedback");
      feedback.style.display = "none";
      var answered = false;

      q.options.forEach(function(opt){
        var b = document.createElement("button");
        b.type = "button";
        b.className = "opt";
        b.textContent = opt.text;
        b.addEventListener("click", function(){
          if(answered) return;
          answered = true;
          var buttons = list.querySelectorAll(".opt");
          buttons.forEach(function(btn){ btn.disabled = true; });
          if(opt.correct){
            b.classList.add("correct");
            feedback.className = "feedback correct";
            feedback.textContent = q.correctFeedback || ("Correct. " + (q.explain || ""));
            solvedCount++;
            if(solvedCount === data.questions.length && onComplete) onComplete();
          } else {
            b.classList.add("incorrect");
            feedback.className = "feedback incorrect";
            feedback.textContent = q.incorrectFeedback || ("Not quite. " + (q.explain || ""));
            var correctBtn = Array.prototype.find.call(buttons, function(btn, i){
              return q.options[i].correct;
            });
            if(correctBtn) correctBtn.classList.add("correct");
          }
          feedback.style.display = "block";
        });
        list.appendChild(b);
      });

      item.appendChild(list);
      item.appendChild(feedback);
      wrap.appendChild(item);
    });

    container.appendChild(wrap);
  }

  /* ---------------- SEQUENCE ---------------- */
  function renderSequence(container, data, onComplete){
    container.innerHTML = "";
    var wrap = el("div", "activity");
    if(data.prompt){ wrap.appendChild(el("p", "q", data.prompt)); }

    var track = el("div", "seq-track");
    var pool = el("div", "seq-pool");
    var feedback = el("div", "feedback");
    feedback.style.display = "none";

    var items = data.items.slice();
    // shuffle deterministically-ish
    items.sort(function(){ return Math.random() - 0.5; });

    var checkBtn = document.createElement("button");
    checkBtn.type = "button";
    checkBtn.className = "btn btn-primary btn-small";
    checkBtn.textContent = "Check order";
    checkBtn.style.marginTop = "12px";

    function renderPool(){
      pool.innerHTML = "";
      items.forEach(function(it){
        var chip = el("div", "seq-chip", it.label);
        chip.addEventListener("click", function(){
          items = items.filter(function(x){ return x.id !== it.id; });
          track.appendChild(makeTrackChip(it));
          renderPool();
          renderTrackNumbers();
        });
        pool.appendChild(chip);
      });
    }

    function makeTrackChip(it){
      var chip = el("div", "seq-chip");
      var n = el("span", "n", "");
      chip.appendChild(n);
      chip.appendChild(document.createTextNode(it.label));
      chip.dataset.id = it.id;
      chip.addEventListener("click", function(){
        chip.remove();
        items.push(it);
        renderPool();
        renderTrackNumbers();
      });
      return chip;
    }

    function renderTrackNumbers(){
      Array.prototype.forEach.call(track.children, function(chip, i){
        chip.querySelector(".n").textContent = (i + 1) + ".";
      });
    }

    checkBtn.addEventListener("click", function(){
      var order = Array.prototype.map.call(track.children, function(c){ return c.dataset.id; });
      var correct = order.length === data.correctOrder.length &&
        order.every(function(id, i){ return id === data.correctOrder[i]; });
      feedback.style.display = "block";
      if(correct){
        feedback.className = "feedback correct";
        feedback.textContent = data.correctFeedback || "That's the correct order.";
        if(onComplete) onComplete();
      } else {
        feedback.className = "feedback incorrect";
        feedback.textContent = data.incorrectFeedback || "Not quite the right order yet -- click a step in your track to send it back and try again.";
      }
    });

    renderPool();
    wrap.appendChild(el("div", null, "Pool (click to add):"));
    wrap.appendChild(pool);
    wrap.appendChild(el("div", null, "Your order (click a chip to remove it):"));
    wrap.appendChild(track);
    wrap.appendChild(checkBtn);
    wrap.appendChild(feedback);
    container.appendChild(wrap);
  }

  /* ---------------- MATCH ---------------- */
  function renderMatch(container, data, onComplete){
    container.innerHTML = "";
    var wrap = el("div", "activity");
    if(data.prompt){ wrap.appendChild(el("p", "q", data.prompt)); }

    var grid = el("div", "match-grid");
    var leftCol = el("div", "match-col");
    var rightCol = el("div", "match-col");
    leftCol.appendChild(el("h4", null, data.leftLabel || "Roles"));
    rightCol.appendChild(el("h4", null, data.rightLabel || "Tasks"));

    var feedback = el("div", "feedback");
    feedback.style.display = "none";

    var selectedLeft = null;
    var pairedCount = 0;
    var rightItems = data.right.slice().sort(function(){ return Math.random() - 0.5; });

    var leftEls = {}, rightEls = {};

    data.left.forEach(function(l){
      var d = el("div", "match-item", l.label);
      d.dataset.id = l.id;
      d.addEventListener("click", function(){
        if(d.classList.contains("paired")) return;
        Object.keys(leftEls).forEach(function(k){ leftEls[k].classList.remove("selected"); });
        selectedLeft = l.id;
        d.classList.add("selected");
      });
      leftEls[l.id] = d;
      leftCol.appendChild(d);
    });

    rightItems.forEach(function(r){
      var d = el("div", "match-item", r.label);
      d.dataset.id = r.id;
      d.addEventListener("click", function(){
        if(d.classList.contains("paired") || !selectedLeft) return;
        var isMatch = data.pairs[selectedLeft] === r.id;
        if(isMatch){
          d.classList.add("paired");
          leftEls[selectedLeft].classList.add("paired");
          leftEls[selectedLeft].classList.remove("selected");
          pairedCount++;
          selectedLeft = null;
          feedback.style.display = "block";
          feedback.className = "feedback correct";
          feedback.textContent = "Matched.";
          if(pairedCount === data.left.length){
            feedback.textContent = data.completeFeedback || "All matched correctly.";
            if(onComplete) onComplete();
          }
        } else {
          d.classList.add("wrong-flash");
          feedback.style.display = "block";
          feedback.className = "feedback incorrect";
          feedback.textContent = data.wrongFeedback || "That's not the right pairing -- try again.";
          setTimeout(function(){ d.classList.remove("wrong-flash"); }, 500);
        }
      });
      rightEls[r.id] = d;
      rightCol.appendChild(d);
    });

    grid.appendChild(leftCol);
    grid.appendChild(rightCol);
    wrap.appendChild(grid);
    wrap.appendChild(feedback);
    container.appendChild(wrap);
  }

  /* ---------------- WORK SAMPLE (portfolio Apply step) ---------------- */
  function renderWorkSample(container, data, onComplete){
    container.innerHTML = "";
    var wrap = el("div", "activity worksample");

    if(data.intro){ wrap.appendChild(el("p", "q", data.intro)); }

    var textareas = [];
    data.fields.forEach(function(f){
      var fieldWrap = el("div", "ws-field");
      fieldWrap.appendChild(el("label", "ws-label", f.label));
      var ta = document.createElement("textarea");
      ta.className = "ws-textarea";
      ta.placeholder = f.placeholder || "";
      ta.rows = f.rows || 3;
      fieldWrap.appendChild(ta);
      textareas.push({ id: f.id, label: f.label, el: ta });
      wrap.appendChild(fieldWrap);
    });

    var warning = el("div", "feedback incorrect", "Fill in every section before generating your work sample.");
    warning.style.display = "none";

    var genBtn = document.createElement("button");
    genBtn.type = "button";
    genBtn.className = "btn btn-primary btn-small";
    genBtn.textContent = "Generate my work sample";
    genBtn.style.marginTop = "6px";

    var previewWrap = el("div", "ws-preview-wrap");
    previewWrap.style.display = "none";
    var previewLabel = el("div", "ws-preview-label", "Your work sample:");
    var preview = document.createElement("pre");
    preview.className = "ws-preview";
    var copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "btn btn-ghost btn-small";
    copyBtn.textContent = "Copy work sample";
    copyBtn.style.marginTop = "8px";
    var saveNote = el("div", "ws-save-note", "This site doesn't store what you write -- copy this into your own document or portfolio file to keep it.");
    previewWrap.appendChild(previewLabel);
    previewWrap.appendChild(preview);
    previewWrap.appendChild(copyBtn);
    previewWrap.appendChild(saveNote);

    genBtn.addEventListener("click", function(){
      var allFilled = textareas.every(function(t){ return t.el.value.trim().length > 0; });
      if(!allFilled){
        warning.style.display = "block";
        return;
      }
      warning.style.display = "none";
      var lines = [data.title || "Work Sample"];
      lines.push("");
      textareas.forEach(function(t){
        lines.push(t.label + ":");
        lines.push(t.el.value.trim());
        lines.push("");
      });
      preview.textContent = lines.join("\n");
      previewWrap.style.display = "block";
      if(onComplete) onComplete();
    });

    copyBtn.addEventListener("click", function(){
      var text = preview.textContent;
      var done = function(){
        copyBtn.textContent = "Copied";
        setTimeout(function(){ copyBtn.textContent = "Copy work sample"; }, 1500);
      };
      if(navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(text).then(done).catch(function(){});
      } else {
        var ta2 = document.createElement("textarea");
        ta2.value = text;
        document.body.appendChild(ta2);
        ta2.select();
        try{ document.execCommand("copy"); }catch(e){}
        document.body.removeChild(ta2);
        done();
      }
    });

    wrap.appendChild(genBtn);
    wrap.appendChild(warning);
    wrap.appendChild(previewWrap);
    container.appendChild(wrap);
  }

  window.PVAActivities = {
    renderQuiz: renderQuiz,
    renderSequence: renderSequence,
    renderMatch: renderMatch,
    renderWorkSample: renderWorkSample
  };
})();
