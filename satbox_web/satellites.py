"""Per-user satellite selection; calculation remains in the prediction service."""
from flask import Blueprint,current_app,g,render_template,request,redirect,url_for,flash
from .auth import login_required

satellites = Blueprint('satellites',__name__)


@satellites.route('/satellites',methods=['GET','POST'])
@login_required
def selection():
    predictions = current_app.extensions['predictions']
    try:
        config,_,records = predictions.catalog(all_records=True)
        names = sorted({r.name for r in records},key=str.casefold)
        selected = predictions.selected_names(g.user,config,records)
        error = None
        if request.method == 'POST':
            selected = request.form.getlist('satellites')
            if len(selected) != len(set(selected)) or not set(selected).issubset(names):
                error = '利用可能な衛星だけを選択してください。TLEがない衛星は選択から外してください。'
            else:
                current_app.extensions['users'].select_satellites(g.user['id'],selected)
                flash(f'{len(selected)}衛星を保存しました。通知対象から外れた衛星の通知予定も解除しました。')
                return redirect(url_for('satellites.selection'))
        return render_template('satellites.html',available=[n for n in names if n not in selected],
                               selected=selected,missing=set(selected)-set(names),error=error)
    except (OSError,ValueError,UnicodeError):
        current_app.logger.exception('Cannot load satellite catalog')
        return render_template('error.html'),503
