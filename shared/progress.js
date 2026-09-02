/* PVA Free Training -- E-commerce VA Foundations
   Progress tracking (localStorage). Isolated key/namespace so this
   pathway can never collide with General Admin / Customer Support / SMM. */

(function(){
  var KEY = "pva-ecom-ft-progress";

  function read(){
    try{
      var raw = window.localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : { lessons: {}, modules: {} };
    }catch(e){
      return { lessons: {}, modules: {} };
    }
  }

  function write(state){
    try{ window.localStorage.setItem(KEY, JSON.stringify(state)); }
    catch(e){ /* storage unavailable -- fail silently, course still works */ }
  }

  var PVAEcom = {
    /* lessonId like "m1-l3" */
    isLessonDone: function(lessonId){
      var s = read();
      return !!s.lessons[lessonId];
    },
    markLessonDone: function(lessonId){
      var s = read();
      s.lessons[lessonId] = true;
      write(s);
    },
    lessonsDoneInModule: function(moduleId, lessonIds){
      var s = read();
      return lessonIds.filter(function(id){ return !!s.lessons[id]; }).length;
    },
    resetAll: function(){
      write({ lessons: {}, modules: {} });
    }
  };

  window.PVAEcom = PVAEcom;
})();
