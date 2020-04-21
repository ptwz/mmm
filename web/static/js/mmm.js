
$(function() {
	// CSRF stuff taken from flask-wtf.readthedocs.io
	let csrf_token = $("[data-csrf]").data('csrf');
	$.ajaxSetup({
		beforeSend: function(xhr, settings) {
			if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
				xhr.setRequestHeader("X-CSRFToken", csrf_token);
			}
		}
	});

	$('div.play').click(function(event){
		let data = $(event.target).data();
		$.post('/music/control/play', data, function(){
			console.log("Update seems to have worked..");
		});

		console.log();
	});
	$('form[data-usage="assign_tag"]').submit(function(event) {
		let form = event.target;

		let data = {"AJAX": true};
		$("input", form).each(function(){
			data[this.name] = this.value;
		});
		let dest_url = form.action;
		$.post(dest_url, data, function(){
			console.log("Update seems to have worked..");
		});
		// TODO: .fail(function() {....} ) 
		event.preventDefault();
		/*$.getJSON('/music/playlist/assign/', {
			a: $('input[name="a"]').val(),
			b: $('input[name="b"]').val()
		}, function(data) {
			$("#result").text(data.result);
		});
		*/
		return false;
	});
});
