$(function() {
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
