(function(){
  function applyTheme(t){
    document.documentElement.setAttribute('data-theme', t);
    var b=document.getElementById('theme-toggle'); if(b) b.textContent=(t==='dark')?'\u2600':'\u263E';
    try{localStorage.setItem('summa-theme', t);}catch(e){}
  }
  applyTheme(document.documentElement.getAttribute('data-theme')||'light');
  var b=document.getElementById('theme-toggle');
  if(b) b.addEventListener('click',function(){applyTheme(document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark');});
})();
